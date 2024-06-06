import uvicorn
import time
import requests
from configobj import ConfigObj
from fastapi import FastAPI, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
app = FastAPI()
ini = ConfigObj('conf.ini', encoding="UTF8")

def handle_monitor_task(cursor: str):
    result = ini.reload()
    name = ini["name"]
    print(name)

@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(None), cursor: str = Form()):
    background_tasks.add_task(handle_monitor_task, cursor)
    return {"message": "请求成功"}


if __name__ == '__main__':
    uvicorn.run("test:app", host="0.0.0.0", port=8000, reload=True)
