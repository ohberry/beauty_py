import asyncio
import csv
import io
import os
import time
from loguru import logger
import aiohttp
from aiohttp import web
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

progress = Progress(
    TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",
    "•",
    DownloadColumn(),
    "•",
    TransferSpeedColumn(),
    # "•",
    # TimeRemainingColumn(),
)
done_event = asyncio.Event()
semaphore = asyncio.Semaphore(3)

dy_headers = {
    'Referer': 'https://www.douyin.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 '
                  'Safari/537.36'
}


async def download(url, path, task_id, work_id):
    # proxy = "http://127.0.0.1:7890"
    async with semaphore:
        # connector = aiohttp.TCPConnector(limit=2)
        # async with aiohttp.ClientSession(connector=connector) as session:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=dy_headers) as resp:
                if resp.status != 200:
                    logger.error(f"Unexpected status code: {resp.status}")
                file_size = int(resp.headers['content-length'])
                progress.update(total=file_size, task_id=task_id)
                with open(path, 'wb') as f:
                    progress.start_task(task_id)
                    while not done_event.is_set():
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        progress.update(task_id, advance=len(chunk))


async def test(file):
    content = file.file.read()
    string_io = io.StringIO(content.decode('utf-8'))
    reader = csv.DictReader(string_io)
    base_path = 'E:\\迅雷云盘\\douyin'
    tasks = []
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
            task_id = progress.add_task(description='Download', filename=download_path, start=False)
            task = asyncio.create_task(download(url, download_path, task_id, aweme_id))
            tasks.append(task)
        elif aweme_type == 'image':
            download_folder = os.path.join(base_path, f'{create_time}@{aweme_id}')
            if not os.path.exists(download_folder):
                os.makedirs(download_folder)
            number = row['序号']
            url = row['下载链接']
            download_path = os.path.join(download_folder, f'{number}.webp')
            task_id = progress.add_task(description='Download', filename=download_path, start=False)
            task = asyncio.create_task(download(url, download_path, task_id, aweme_id))
            tasks.append(task)
        else:
            logger.error(f'type: {aweme_type} is not supported')
    with progress:
        await asyncio.gather(*tasks)
        logger.info("All tasks have been completed.")


async def hello(request):
    data = await request.post()
    file = data['file']
    asyncio.create_task(test(file))
    return web.json_response({'status': 'ok'})


app = web.Application()
app.add_routes([web.post('/data', hello)])

# cors = aiohttp_cors.setup(app)
# resource = cors.add(app.router.add_resource("/data"))
#
# route = cors.add(
#     resource.add_route("POST", hello), {
#         "*": aiohttp_cors.ResourceOptions(
#             allow_credentials=True,
#             expose_headers="*",
#             allow_headers="*",
#             max_age=3600,
#         )
#     })

if __name__ == '__main__':
    web.run_app(app)
