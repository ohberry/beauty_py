import csv
import io
import json
import os
import random
import re
import sys
import time
import execjs
from fastapi import FastAPI, BackgroundTasks, Form, Request, File
from fastapi.responses import JSONResponse
import uvicorn
import utils
from xbogus import XBogus
from configobj import ConfigObj
from loguru import logger
import requests
from datetime import datetime
from tqdm import tqdm
import urllib.parse
from abogus import ABogus, BrowserFingerprintGenerator

root_path = os.getcwd()
# print(root_path)
sys.path.append(root_path)

ini = ConfigObj('conf.ini', encoding="UTF8")

dy_headers = {
    'Cookie': ini['dyCookie'],
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0'
}

xb = XBogus(dy_headers['User-Agent'])
browser_fp = BrowserFingerprintGenerator.generate_fingerprint("Edge")
abogus = ABogus(user_agent=dy_headers['User-Agent'], fp=browser_fp)

dy_download_headers = {
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 '
                  'Safari/537.36'
}

dy_post_params = {
    "device_platform": "webapp",
    "aid": "6383",
    "channel": "channel_pc_web",
    "pc_client_type": 1,
    "version_code": "190500",
    "version_name": "19.5.0",
    "cookie_enabled": "true",
    "screen_width": 1920,
    "screen_height": 1080,
    "browser_language": "zh-CN",
    "browser_platform": "Win32",
    "browser_name": "Edge",
    "browser_version": "122.0.0.0",
    "browser_online": "true",
    "engine_name": "Blink",
    "engine_version": "122.0.0.0",
    "os_name": "Windows",
    "os_version": "10",
    "cpu_core_num": 12,
    "device_memory": 8,
    "platform": "PC",
    "downlink": "10",
    "effective_type": "4g",
    "round_trip_time": 100,
    "webid": "7333282344759494196",
}

js = execjs.compile(open(r'./xhs.js', 'r', encoding='utf-8').read())

xhs_common_headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "content-type": "application/json;charset=UTF-8",
    "dnt": "1",
    "origin": "https://www.xiaohongshu.com",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://www.xiaohongshu.com/",
    "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
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

xhs_post_url = 'https://edith.xiaohongshu.com'

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

app = FastAPI()


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "系统异常"}
    )


def download(url, path, work_id):
    for i in range(3):
        resp = requests.get(url, timeout=20, stream=True, headers=dy_download_headers)
        code = resp.status_code
        if code != 200:
            if code != 429:
                raise Exception(f"下载请求异常，状态码: {resp.status_code}")
            else:
                if i == 2:
                    raise Exception(f"下载请求异常，状态码: {resp.status_code}")
                logger.error(f"第{i + 1}次尝试：等待2s后重试")
                time.sleep(2)
                continue
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    break
                f.write(chunk)
        logger.info(f'have downloaded {url} 作品id：{work_id} {path}')
        return


def download_progress(url, path, file_ext, headers=None):
    for i in range(3):
        resp = requests.get(url, timeout=20, stream=True, headers=headers)
        code = resp.status_code
        if code != 200:
            if code != 429:
                raise Exception(f"下载请求异常，状态码: {resp.status_code}")
            else:
                if i == 2:
                    raise Exception(f"下载请求异常，状态码: {resp.status_code}")
                logger.error(f"第{i + 1}次尝试：等待2s后重试")
                time.sleep(2)
                continue
            # 获取文件总大小
        total_size = int(resp.headers.get('content-length', 0))
        content_type = resp.headers.get('Content-Type')
        if 'image/jpeg' in content_type:
            file_ext = '.jpg'
        elif 'image/png' in content_type:
            file_ext = '.png'
        elif 'image/webp' in content_type:
            file_ext = '.webp'
        elif 'video/mp4' in content_type:
            file_ext = '.mp4'
        file_path = f'{path}{file_ext}'
        with open(file_path, 'wb') as f, tqdm(
                desc=file_path,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                colour='green'
        ) as bar:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    break
                size = f.write(chunk)
                bar.update(size)
        return


async def handle_monitor_task(link: str, cursor: str = None):
    if link.find('douyin') != -1:
        match = re.search(r'(?<=user/)[\w|-]+', link)
        if not match:
            logger.error('invalid link')
            return
        sec_uid = match.group()
        if cursor is None:
            cursor = 0
        await handle_dy(sec_uid, cursor)
    elif link.find('xiaohongshu') != -1:
        user_id = link.split('/')[-1]
        if cursor is None:
            cursor = ''
        await handle_xhs(user_id, cursor)
    else:
        logger.error(f'不支持的网站：{link}')


async def handle_dy(sec_uid, max_cursor):
    has_more = 1
    page = 0
    temp_time = 0
    temp_cursor = -1
    while has_more == 1:
        if temp_cursor == max_cursor:
            logger.error("页码重复")
            return
        temp_cursor = max_cursor
        logger.info(f'{sec_uid}-{max_cursor}页开始下载:')
        post_params = {"msToken": get_mstoken(), "sec_user_id": sec_uid, "max_cursor": max_cursor}
        post_params.update(dy_post_params)
        query = '&'.join([f'{k}={v}' for k, v in post_params.items()])
        xbogus = xb.getXBogus(query)

        query_params = xbogus[0]
        response = None
        for i in range(3):
            response = requests.get(f'https://www.douyin.com/aweme/v1/web/aweme/post/?{query_params}',
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
        # 可能存在返回的json只有status_code且为0，不知道什么原因造成的
        if not has_more:
            logger.error(f'{sec_uid}-接口返回异常，无其他数据')
            return

        aweme_list = awemes['aweme_list']
        if not aweme_list:
            time.sleep(3)
            continue
        aweme = aweme_list[0]
        author = aweme['author']
        uid = author['uid']
        nickname = author['nickname']
        sub = sec_uid[-6:]
        base_path = os.path.join(ini['dyDownloadDir'], f'{uid}@{nickname}[{sub}]')
        if max_cursor == 0:
            try:
                temp_time = utils.get_local_time(uid, ini['dyDownloadDir'])
                temp_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(temp_time))
                logger.info(f'{sec_uid}-本地时间：{temp_time_str}')
            except Exception as e:
                logger.error(f'{sec_uid}-获取本地时间失败-{e}')
                return
            if not os.path.exists(base_path):
                os.makedirs(base_path)
        max_cursor = awemes['max_cursor']
        for index, aweme in enumerate(aweme_list):
            aweme_id = aweme['aweme_id']
            is_top = aweme['is_top']
            # 时间戳秒
            create_time = aweme['create_time']

            # 如果本地最新的时间大于create_time，则说明该作品已经下载过，跳过
            if temp_time >= create_time:
                if is_top == 1:
                    continue
                logger.info(f'{sec_uid} {nickname}-无新作品')
                return
            aweme_type = aweme['aweme_type']
            time_format = time.strftime('%Y%m%d%H%M%S', time.localtime(create_time))

            if aweme_type in video_type:
                video_url = aweme['video']['bit_rate'][0]['play_addr']['url_list'][0]
                save_path = os.path.join(base_path, f'{time_format}@{aweme_id}')
                try:
                    # download(video_url, save_path, aweme_id)
                    download_progress(video_url, save_path, '.mp4', dy_download_headers)
                except Exception as e:
                    logger.error(f'{sec_uid}-{save_path} {video_url}下载视频失败，原因：{e}')


            elif aweme_type in img_type:
                img_path = os.path.join(base_path, f'{time_format}@{aweme_id}')
                if not os.path.exists(img_path):
                    os.makedirs(img_path)
                images = aweme['images']
                for j, img in enumerate(images):
                    img_url = img['url_list'][0]
                    save_path = os.path.join(img_path, f'{j}')
                    try:
                        # download(img_url, save_path, aweme_id)
                        download_progress(img_url, save_path, '.webp', dy_download_headers)
                    except Exception as e:
                        logger.error(f'{sec_uid}-{save_path}-{img_url}下载视频失败，原因：{e}')
                    time.sleep(1)

            else:
                logger.error(f'{nickname}-出现了未知类型-{aweme_type}:作品时间{time_format},作品id：{aweme_id}')
                continue
            time.sleep(2)
        page += 1
    logger.info(f'{sec_uid}到底了')


def get_mstoken():
    base_str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-'
    return "".join(random.choice(base_str) for _ in range(126)) + '=='


async def handle_xhs(user_id, cursor=''):
    headers = {'cookie': ini["xhsCookie"]}
    headers.update(xhs_common_headers)
    has_more = True
    while has_more:
        logger.info(f"{user_id}-{cursor}页 开始下载")
        api = f"/api/sns/web/v1/user_posted?num=30&cursor={cursor}&user_id={user_id}&image_formats=jpg,webp,avif&id=1"
        ret = js.call('sign', api, None, ini["xhsCookie"])
        headers.update(ret)

        res = requests.get(f'{xhs_post_url}{api}', headers=headers)
        if res.status_code != 200:
            logger.error(f"{user_id} 请求分页数据 Unexpected status code: {res.status_code}")
            return
        page_info = res.json()
        is_success = page_info['success']
        if not is_success:
            logger.error(f"{user_id} 请求分页数据返回状态不正常")
            return
        has_more = page_info['data']['has_more']
        cursor = page_info['data']['cursor']
        notes = page_info['data']['notes']
        if not notes:
            time.sleep(2)
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
            get_one_note(note_id)
            time.sleep(2)
    logger.info(f"{user_id}-{cursor} 下载已完成")


def get_one_note(note_id):
    headers = {'cookie': ini['xhsCookie']}
    headers.update(xhs_common_headers)
    resp =requests.get("https://www.xiaohongshu.com/explore", headers=headers)
    if resp.status_code != 200 or resp.text == '':
        return {}, False
    pattern = r'xsec_token=(.*?)&'
    match = re.search(pattern, resp.text)
    if not match:
        logger.error("No xsec_token match found.")
        return {}, False
    xsec_token = match.group(1)
    params = {"source_note_id": note_id, "image_formats": [
        "jpg", "webp", "avif"], "extra": {"need_body_topic": "1"}, "xsec_source": "pc_feed", "xsec_token": xsec_token}
    ret = js.call('sign', '/api/sns/web/v1/feed', params, ini['xhsCookie'])
    data = json.dumps(params, separators=(',', ':'), ensure_ascii=False)
    headers.update(ret)
    try:
        response = requests.post('https://edith.xiaohongshu.com/api/sns/web/v1/feed', headers=headers,
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
        try:
            download_progress(video_url, os.path.join(save_path, f'{upload_time_str}@{note_id}'), ".mp4")
        except Exception as e:
            logger.error(f'{user_id}-{save_path}-{video_url}下载视频失败，原因：{e}')

    elif note_type == 'normal':
        images = note['note_card']['image_list']
        os.mkdir(os.path.join(save_path, f'{upload_time_str}@{note_id}'))
        for index, img in enumerate(images):
            img_url = img['info_list'][0]['url']
            trace_id = img_url.split('/')[-1].split('!')[0]
            no_watermark_img_url = f'{random.choice(xhs_img_cdns)}/{trace_id}?imageView2/format/png'
            try:
                download_progress(no_watermark_img_url,
                                  os.path.join(save_path, f'{upload_time_str}@{note_id}', f'{index}'),
                                  ".png")
            except Exception as e:
                logger.error(f'{user_id}-{save_path}-{img_url}下载视频失败，原因：{e}')

    else:
        logger.error(f'笔记 {note_id} 类型未知')


def get_one_aweme(item_id):
    post_params = {"aweme_id": item_id, "msToken": get_mstoken()}
    post_params.update(dy_post_params)
    query = '&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in post_params.items()])
    ab = abogus.generate_abogus(query, "GET")
    params = ab[0]
    resp = requests.get(f'https://www.douyin.com/aweme/v1/web/aweme/detail/?{params}', headers=dy_headers)
    info_json = resp.json()
    nickname = info_json['aweme_detail']['author']['nickname']
    uid = info_json['aweme_detail']['author']['uid']
    sec_uid = info_json['aweme_detail']['author']['sec_uid']
    create_time = info_json['aweme_detail']['create_time']
    aweme_type = info_json['aweme_detail']['aweme_type']
    base_path = os.path.join(ini['dyDownloadDir'], f'{uid}@{nickname}[{sec_uid[-6:]}]')
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    time_format = time.strftime('%Y%m%d%H%M%S', time.localtime(create_time))
    if aweme_type in img_type:
        img_path = os.path.join(base_path, f'{time_format}@{item_id}')
        os.makedirs(img_path)
        images = info_json['aweme_detail']['images']
        for j, img in enumerate(images):
            img_url = img['url_list'][0]
            download(img_url, os.path.join(img_path, f'{j}.webp'), item_id)
    elif aweme_type in video_type:
        video_url = info_json['aweme_detail']['video']['bit_rate'][0]['play_addr']['url_list'][0]
        download(video_url, os.path.join(base_path, f'{time_format}@{item_id}.mp4'), item_id)
    else:
        logger.error(f'{nickname}-出现了未知类型-{aweme_type}:作品时间{time_format},作品id：{item_id}')
    pass


def parse_csv(content):
    string_io = io.StringIO(content)
    reader = csv.DictReader(string_io)
    base_path = ini['dyDownloadDir']
    for index, row in enumerate(reader):
        aweme_type = row['aweme_type']
        sec_uid = row['sec_uid']
        uid = row['uid']
        nickname = row['nickname']
        aweme_id = row['作品id']
        if index == 0:
            sub = sec_uid[-6:]
            base_path = os.path.join(base_path, f'{uid}@{nickname}[{sub}]')
            if not os.path.exists(base_path):
                os.makedirs(base_path)

        create_time = time.strptime(row['发布时间'], '%Y-%m-%d %H:%M:%S')
        create_time = time.strftime('%Y%m%d%H%M%S', create_time)
        if aweme_type == 'video':
            url = row['下载链接']
            download_path = os.path.join(base_path, f'{create_time}@{aweme_id}')
            download_progress(url, download_path, aweme_id, '.mp4')
        elif aweme_type == 'image':
            download_folder = os.path.join(base_path, f'{create_time}@{aweme_id}')
            if not os.path.exists(download_folder):
                os.makedirs(download_folder)
            number = row['序号']
            url = row['下载链接']
            download_path = os.path.join(download_folder, number)
            download_progress(url, download_path, aweme_id, '.webp')
        else:
            logger.error(f'type: {aweme_type} is not supported')
    logger.info("All have been completed.")


@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(), cursor: str = Form(None)):
    background_tasks.add_task(handle_monitor_task, link, cursor)
    return {"message": "请求成功"}


@app.post("/single")
async def single(background_tasks: BackgroundTasks, item_id: str = Form()):
    background_tasks.add_task(get_one_aweme, item_id)
    return {"message": "请求成功"}


@app.post("/batch")
async def batch(background_tasks: BackgroundTasks, file: bytes = File()):
    content = file.decode('utf-8')
    background_tasks.add_task(parse_csv, content)
    return {"message": "请求成功"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8899, reload=False)
    # name_app = os.path.basename(__file__)[0:-3]
    # uvicorn.run(f"{Path(__file__).stem}:app", host="0.0.0.0", port=8899, reload=False)
