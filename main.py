import os
import re
import time
from contextlib import asynccontextmanager

import aiohttp
import asyncio
from fastapi import FastAPI, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import uvicorn

from XB import XBogus
from configobj import ConfigObj
from loguru import logger
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich import print

progress = Progress(
    TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",
    "•",
    DownloadColumn(),
    "•",
    TransferSpeedColumn(),
    "•",
    TimeRemainingColumn(),
)


xb = XBogus()

redis_client: redis.client.Redis
client_session: aiohttp.ClientSession
ini = ConfigObj('conf.ini', encoding="UTF8")

dy_headers = {
    'Cookie': ini['dyCookie'],
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 '
                  'Safari/537.36'
}

# 抖音作品类型
video_type = (0, 4, 51, 53, 55, 58, 61, 66, 109)
img_type = (2, 68, 150)

logger.add('xhs_{time:%Y%m%d}_info.log', level="INFO", rotation='1 day',
           retention='5 days',
           backtrace=True, diagnose=True,
           encoding='utf-8', filter=lambda record: record["level"].name == "INFO")
logger.add('xhs_{time:%Y%m%d}_error.log', level="ERROR", rotation='1 day',
           retention='5 days',
           backtrace=True, diagnose=True,
           encoding='utf-8', filter=lambda record: record["level"].name == "ERROR")


class UnicornException(Exception):
    def __init__(self, name: str):
        self.name = name


class RedisTemplate:
    @classmethod
    async def get(cls, key: str) -> str:
        result = await redis_client.get(key)
        return result

    @classmethod
    async def set(cls, key: str, value: str):
        await redis_client.set(key, value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    pool = redis.ConnectionPool.from_url("redis://localhost:3278/0")
    redis_client = redis.Redis.from_pool(pool)

    global client_session
    client_session = aiohttp.ClientSession()

    yield
    await redis_client.close()
    await client_session.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(UnicornException)
async def unicorn_exception_handler(request: Request, exc: UnicornException):
    return JSONResponse(
        status_code=400,
        content={"message": exc.name},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "系统异常"}
    )


async def download(url, path, work_id):
    for i in range(3):
        async with client_session.get(url, cookies=None) as response:
            if response.status != 200:
                if i == 2:
                    logger.error(f'{url}-请求作品信息失败,状态码：{response}')
                    return
            else:
                with open(path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                logger.info(f'have downloaded {url} 作品id：{work_id} {path}')
                break


async def handle_monitor_task(link: str, cursor: str = None):
    if link.find('douyin') != -1:
        match = re.search(r'(?<=user/)[\w|-]+', link)
        if not match:
            raise Exception('invalid link')
        sec_uid = match.group()
        if cursor is None:
            cursor = 0
        await handle_dy(sec_uid, cursor)


async def handle_dy(sec_uid: str, max_cursor: str):
    has_more = 1
    page = 0
    local_latest_time = 0
    while has_more == 1:
        logger.info(f'{sec_uid}-{max_cursor}页开始下载:')
        post_params = xb.getXBogus(f'aid=6383&sec_user_id'
                                   f'={sec_uid}&count=20&max_cursor={max_cursor}&cookie_enabled=true'
                                   '&platform=PC&downlink=10')
        for i in range(3):
            async with client_session.get(f'https://www.douyin.com/aweme/v1/web/aweme/post/?{post_params}',
                                          headers=dy_headers) as response:
                if response.status == 429:
                    time.sleep(3)
                    if i < 2:
                        continue
                if response.status != 200 or response.text == '':
                    logger.error(f'{sec_uid}-请求作品信息失败,状态码：{response}')
                    return
                if response.status == 200:
                    awemes = await response.json()
                    break
        if not awemes:
            logger.error(f'{sec_uid}-请求作品信息失败,请检查用户是否异常或者请求频繁导致cookie被ban')
        if awemes['status_code'] != 0:
            logger.error(f'{sec_uid}-作品信息接口返回不正常,状态码：{awemes["status_code"]}')

        has_more = awemes['has_more']
        aweme_list = awemes['aweme_list']
        max_cursor = awemes['max_cursor']
        if not aweme_list:
            time.sleep(5)
            continue
        aweme = aweme_list[0]
        author = aweme['author']
        uid = author['uid']
        nickname = author['nickname']
        sub = sec_uid[-6:]
        base_path = os.path.join(ini['dyDownloadDir'], f'{uid}@{nickname}[{sub}]')
        if page == 0:
            local_latest_time = await RedisTemplate.get(f'{sec_uid}')
            if not local_latest_time:
                local_latest_time = 0
            if not os.path.exists(base_path):
                os.makedirs(base_path)
        for index, aweme in enumerate(aweme_list):
            aweme_id = aweme['aweme_id']
            is_top = aweme['is_top']
            create_time = aweme['create_time']

            if local_latest_time >= create_time:
                if is_top == 1:
                    continue
                logger.info(f'{sec_uid} {nickname}-无新作品')
                return
            if page == 0 and index == 0:
                await RedisTemplate.set(f'{sec_uid}', str(create_time))

            aweme_type = aweme['aweme_type']
            time_format = time.strftime('%Y%m%d%H%M%S', time.localtime(create_time))
            if aweme_type in video_type:
                video_url = aweme['video']['bit_rate'][0]['play_addr']['url_list'][0]
                await download(video_url, os.path.join(base_path, f'{time_format}@{aweme_id}.mp4'), aweme_id)

            elif aweme_type in img_type:
                img_path = os.path.join(base_path, f'{time_format}@{aweme_id}')
                if not os.path.exists(img_path):
                    os.makedirs(img_path)
                images = aweme['images']
                for j, img in enumerate(images):
                    img_url = img['url_list'][0]
                    await download(img_url, os.path.join(img_path, f'{j}.webp'), aweme_id)
            else:
                logger.error(f'{nickname}-出现了未知类型-{aweme_type}:作品时间{time_format},作品id：{aweme_id}')
                continue
            time.sleep(1)
        page += 1
    logger.info(f'{sec_uid}到底了')


@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(), cursor: str = Form()):
    background_tasks.add_task(handle_monitor_task, link, cursor)
    return {"message": "请求成功"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
