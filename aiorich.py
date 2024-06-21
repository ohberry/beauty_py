import asyncio
import aiohttp
from aiohttp import web
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
    # "•",
    # TimeRemainingColumn(),
)
done_event = asyncio.Event()
semaphore = asyncio.Semaphore(5)


async def download(url, path, task_id):
    proxy = "http://127.0.0.1:7890"
    async with semaphore:
        # connector = aiohttp.TCPConnector(limit=2)
        # async with aiohttp.ClientSession(connector=connector) as session:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy) as resp:
                if resp.status != 200:
                    raise ValueError(f"Unexpected status code: {resp.status}")
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


async def test():
    link = 'https://github.com/Eugeny/tabby/releases/download/v1.0.207/tabby-1.0.207-linux-armv7l.tar.gz'
    file = 'F:/Quicker.x64.1.40.2.0.msi'
    link2 = 'https://github.com/Eugeny/tabby/releases/download/v1.0.207/tabby-1.0.207-linux-x64.AppImage'
    file2 = 'F:/node-v20.8.1-x64.msi'
    arr = [{'link': link, 'file': file}, {'link': link2, 'file': file2}]
    tasks = []
    for i in arr:
        task_id = progress.add_task(description='Download', filename=i['file'], start=False)
        task = asyncio.create_task(download(i['link'], i['file'], task_id))
        tasks.append(task)
    with progress:
        await asyncio.gather(*tasks, return_exceptions=True)


async def hello(request):
    data = await request.post()
    file = data['file']
    print(file.filename)
    asyncio.create_task(test())
    return web.Response(text='Hello, world')


app = web.Application()
app.add_routes([web.post('/', hello)])

if __name__ == '__main__':
    web.run_app(app)
