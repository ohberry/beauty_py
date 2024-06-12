import json
import os
import random
import re
import time
from contextlib import asynccontextmanager

import execjs
from fastapi import FastAPI, BackgroundTasks, Form, Request, Depends
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import uvicorn
from sqlalchemy.orm import Session

import database
import utils
from XB import XBogus
from configobj import ConfigObj
from loguru import logger
import requests
from datetime import datetime

from database import SessionLocal
from models import History

xb = XBogus()

redis_client: redis.client.Redis

ini = ConfigObj('conf.ini', encoding="UTF8")

dy_headers = {
    'Cookie': ini['dyCookie'],
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 '
                  'Safari/537.36'
}

js = execjs.compile(open(r'./info.js', 'r', encoding='utf-8').read())

xhs_headers = {
    "authority": "edith.xiaohongshu.com",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-s": "",
    "x-t": "",
}

page_params = {
    "num": "30",
    "cursor": "",
    "user_id": "",
    "image_scenes": ""
}
note_body = {
    "source_note_id": '',
    "image_scenes": [
        "CRD_PRV_WEBP",
        "CRD_WM_WEBP"
    ]
}

xhs_img_cdns = [
    "https://sns-img-qc.xhscdn.com",
    "https://sns-img-hw.xhscdn.com",
    "https://sns-img-bd.xhscdn.com",
    "https://sns-img-qn.xhscdn.com",
]

xhs_video_cdns = [
    # "https://sns-video-qc.xhscdn.com",
    "https://sns-video-hw.xhscdn.com",
    "https://sns-video-bd.xhscdn.com",
    "https://sns-video-qn.xhscdn.com",
]

more_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/user_posted'

# 抖音作品类型
video_type = (0, 4, 51, 53, 55, 58, 61, 66, 109)
img_type = (2, 68, 150)

logger.add('beauty_{time:%Y%m%d}_info.log', level="INFO", rotation='1 day',
           retention='30 days',
           backtrace=True, diagnose=True,
           encoding='utf-8', filter=lambda record: record["level"].name == "INFO")
logger.add('beauty_{time:%Y%m%d}_error.log', level="ERROR", rotation='1 day',
           retention='30 days',
           backtrace=True, diagnose=True,
           encoding='utf-8', filter=lambda record: record["level"].name == "ERROR")


def cookie_to_dict(cookie_str):
    # 过滤掉空格，空格可能有多个
    cookie_str = cookie_str.replace(' ', '')
    d = {item.split('=')[0]: item.split('=')[1] for item in cookie_str.split(';')}
    if 'name' in d:
        del d['abRequestId']
    return d


xhs_cookie = cookie_to_dict(ini['xhsCookie'])


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

    yield
    await redis_client.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "系统异常"}
    )


def download(url, path, work_id):
    try:
        for i in range(3):
            resp = requests.get(url, timeout=20, stream=True)
            code = resp.status_code
            if code != 200:
                if code != 429:
                    raise Exception(f"下载请求异常，状态码: {resp.status_code}")
                else:
                    if i == 2:
                        raise Exception(f"下载请求异常，状态码: {resp.status_code}")
                    logger.error(f"第{i + 1}次尝试：下载失败 {url} {path}")
                    time.sleep(3)
                    continue
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        break
                    f.write(chunk)
            logger.info(f'have downloaded {url} 作品id：{work_id} {path}')
            return
    except Exception as e:
        logger.error(f'下载失败，{url} {path}: {e}')
        raise e


async def handle_monitor_task(link: str, cursor: str = None, db: Session = None):
    if link.find('douyin') != -1:
        match = re.search(r'(?<=user/)[\w|-]+', link)
        if not match:
            raise Exception('invalid link')
        sec_uid = match.group()
        if cursor is None:
            cursor = 0
        await handle_dy(sec_uid, cursor, db)


async def handle_dy(sec_uid: str, max_cursor: str, db: Session = None):
    has_more = 1
    page = 0
    local_latest_time = 0
    temp_time = 0
    while has_more == 1:
        logger.info(f'{sec_uid}-{max_cursor}页开始下载:')
        post_params = xb.getXBogus(f'aid=6383&sec_user_id'
                                   f'={sec_uid}&count=20&max_cursor={max_cursor}&cookie_enabled=true'
                                   '&platform=PC&downlink=10')
        response = None
        for i in range(3):
            response = requests.get(f'https://www.douyin.com/aweme/v1/web/aweme/post/?{post_params}',
                                    headers=dy_headers)
            if response.status_code == 429:
                if i < 2:
                    time.sleep(3)
                    continue
            if response.status_code != 200 or response.text == '':
                logger.error(f'{sec_uid}-请求作品列表信息失败,状态码：{response}')
                return
            if response.status_code == 200:
                break
        awemes = response.json()
        if not awemes:
            logger.error(f'{sec_uid}-请求作品信息失败,请检查用户是否异常或者请求频繁导致cookie被ban')
            return

        if awemes['status_code'] != 0:
            logger.error(f'{sec_uid}-请求成功，但接口返回不正常,接口返回码：{awemes["status_code"]}')
            return

        has_more = awemes['has_more']
        if not has_more:
            logger.info(f'{sec_uid}-接口返回异常，无其他数据')
            return

        aweme_list = awemes['aweme_list']
        max_cursor = awemes['max_cursor']
        if not aweme_list:
            time.sleep(3)
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
            else:
                local_latest_time = int(local_latest_time)
            if not os.path.exists(base_path):
                os.makedirs(base_path)
            temp_time = local_latest_time
        for index, aweme in enumerate(aweme_list):
            aweme_id = aweme['aweme_id']
            is_top = aweme['is_top']
            # 时间戳秒
            create_time = aweme['create_time']

            if local_latest_time >= create_time:
                if is_top == 1:
                    continue
                logger.info(f'{sec_uid} {nickname}-无新作品')
                return
            if page == 0:
                if create_time > temp_time and index <= 3:
                    temp_time = create_time
                    await RedisTemplate.set(f'{sec_uid}', str(temp_time))

            aweme_type = aweme['aweme_type']
            time_format = time.strftime('%Y%m%d%H%M%S', time.localtime(create_time))


            if aweme_type in video_type:
                video_url = aweme['video']['bit_rate'][0]['play_addr']['url_list'][0]

                h = History()
                h.platform = 'dy'
                h.sec_uid = sec_uid
                h.user_id = uid
                h.work_id = aweme_id
                h.create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))
                h.work_type = 'video'
                h.url = video_url
                try:
                    download(video_url, os.path.join(base_path, f'{time_format}@{aweme_id}.mp4'), aweme_id)
                    h.status = 1
                except Exception as e:
                    h.status = 0
                db.add(h)
                db.commit()

            elif aweme_type in img_type:
                img_path = os.path.join(base_path, f'{time_format}@{aweme_id}')
                if not os.path.exists(img_path):
                    os.makedirs(img_path)
                images = aweme['images']
                for j, img in enumerate(images):
                    img_url = img['url_list'][0]
                    h = History()
                    h.platform = 'dy'
                    h.sec_uid = sec_uid
                    h.user_id = uid
                    h.work_id = aweme_id
                    h.create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))
                    h.work_type = 'img'
                    h.url = img_url
                    h.index = j
                    try:
                        download(img_url, os.path.join(img_path, f'{j}.webp'), aweme_id)
                        h.status = 1
                    except Exception as e:
                        h.status = 0
                    db.add(h)
                    db.commit()
                    time.sleep(1)

            else:
                logger.error(f'{nickname}-出现了未知类型-{aweme_type}:作品时间{time_format},作品id：{aweme_id}')
                continue
            time.sleep(2)
        page += 1
    logger.info(f'{sec_uid}到底了')


def handle_xhs(user_id, cursor='', db: Session = None):
    has_more = True
    while has_more:
        logger.info(f"{user_id}-{cursor}页 开始下载")
        api = f"/api/sns/web/v1/user_posted?num=30&cursor={cursor}&user_id={user_id}&image_scenes="
        ret = js.call('get_xs', api, '', xhs_cookie['a1'])
        xhs_headers['x-s'], xhs_headers['x-t'] = ret['X-s'], str(ret['X-t'])
        page_params['user_id'] = user_id
        page_params['cursor'] = cursor

        res = requests.get(more_url, params=page_params, headers=xhs_headers, cookies=xhs_cookie)
        if res.status_code != 200:
            raise RuntimeError(f"{user_id} 请求分页数据 Unexpected status code: {res.status_code}")
        page_info = res.json()
        is_success = page_info['success']
        if not is_success:
            raise RuntimeError(f"{user_id} 请求分页数据返回状态不正常")
        has_more = page_info['data']['has_more']
        cursor = page_info['data']['cursor']
        notes = page_info['data']['notes']
        if not notes:
            time.sleep(5)
            logger.info(f"{user_id}-{cursor} 该页无作品")
            continue
        nickname = notes[0]['user']['nickname']
        for index, note in enumerate(notes):
            note_id = note['note_id']
            is_top = note['interact_info']['sticky']
            is_exist = utils.exist(os.path.join(ini['xhsDownloadDir'], f'{user_id}@{nickname}', f'*{note_id}*'))
            if is_exist:
                if is_top:
                    continue
                logger.info(f"{user_id}-{cursor} 无新作品")
                return
            get_one_note(note_id, db)
            time.sleep(5)
    logger.info(f"{user_id}-{cursor} 下载已完成")


def get_one_note(note_id, db):
    note_body['source_note_id'] = note_id
    data = json.dumps(note_body, separators=(',', ':'))
    ret = js.call('get_xs', '/api/sns/web/v1/feed', data, xhs_cookie['a1'])
    xhs_headers['x-s'], xhs_headers['x-t'] = ret['X-s'], str(ret['X-t'])
    try:
        response = requests.post('https://edith.xiaohongshu.com/api/sns/web/v1/feed', headers=xhs_headers,
                                 cookies=xhs_cookie,
                                 data=data)
        note_info = response.json()
        note = note_info['data']['items'][0]
    except Exception as e:
        logger.warning(f'笔记 {note_id} 获取失败: {e}')
        return
    user_id = note['note_card']['user']['user_id']
    nickname = note['note_card']['user']['nickname']
    upload_timestamp = note['note_card']['time']
    # 将时间戳转换为yyyyMMddHHmmss
    upload_time_str = datetime.fromtimestamp(upload_timestamp / 1000).strftime('%Y%m%d%H%M%S')
    note_type = note['note_card']['type']
    save_path = os.path.join(ini['xhsDownloadDir'], f'{user_id}@{nickname}')
    if not os.path.exists(save_path):
        os.makedirs(save_path)


    if note_type == 'video':
        origin_key = note['note_card']['video']['consumer']['origin_video_key']
        video_url = f'{random.choice(xhs_video_cdns)}/{origin_key}'

        h = History()
        h.platform = 'xhs'
        h.user_id = user_id
        h.work_id = note_id
        h.create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(upload_timestamp / 1000))
        h.work_type = 'video'
        h.url = video_url
        try:
            download(video_url, os.path.join(save_path, f'{upload_time_str}@{note_id}.mp4'), note_id)
            h.status = 1
        except Exception as e:
            h.status = 0
        db.commit()

    elif note_type == 'normal':
        images = note['note_card']['image_list']
        os.mkdir(os.path.join(save_path, f'{upload_time_str}@{note_id}'))
        for index, img in enumerate(images):
            img_url = img['info_list'][0]['url']
            trace_id = img_url.split('/')[-1].split('!')[0]
            no_watermark_img_url = f'{random.choice(xhs_img_cdns)}/{trace_id}?imageView2/format/png'

            h = History()
            h.platform = 'xhs'
            h.user_id = user_id
            h.work_id = note_id
            h.create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(upload_timestamp / 1000))
            h.work_type = 'img'
            h.url = img_url
            h.index = index
            try:
                download(no_watermark_img_url, os.path.join(save_path, f'{upload_time_str}@{note_id}', f'{index}.png'),
                         note_id)
                h.status = 1
            except Exception as e:
                h.status = 0
            db.commit()

    else:
        logger.error(f'笔记 {note_id} 类型未知')


@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(), cursor: str = Form(None),
               db: Session = Depends(database.get_db)):
    background_tasks.add_task(handle_monitor_task, link, cursor, db)
    return {"message": "请求成功"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8899, reload=False)
# 如果修改过dy号short_id就会更为为你修改的号码，unique_id为你的dy初始值，uid是相当于用户的身份证唯一码
