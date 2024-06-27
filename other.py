import csv
import os
import time

import requests
from loguru import logger

dy_headers = {
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 '
                  'Safari/537.36'
}


def download(url, path, work_id):
    for i in range(3):
        resp = requests.get(url, timeout=20, stream=True, headers=dy_headers)
        code = resp.status_code
        if code != 200:
            if code != 429:
                logger.error(f"下载请求异常，状态码: {resp.status_code}")
                return
            else:
                if i == 2:
                    logger.error(f"下载请求异常，状态码: {resp.status_code}")
                    return
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


def parse_download():
    base_path = 'E:\\迅雷云盘\\douyin'
    with open(r'test.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
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
                download_path = os.path.join(base_path, f'{create_time}@{aweme_id}.mp4')
                download(url, download_path, aweme_id)
            elif aweme_type == 'image':
                download_folder = os.path.join(base_path, f'{create_time}@{aweme_id}')
                if not os.path.exists(download_folder):
                    os.makedirs(download_folder)
                number = row['序号']
                url = row['下载链接']
                download_path = os.path.join(download_folder, f'{number}.webp')
                download(url, download_path, aweme_id)
            else:
                logger.error(f'type: {aweme_type} is not supported')
            time.sleep(3)
        logger.info('download finished')


if __name__ == '__main__':
    parse_download()
