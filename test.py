import time
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Form, Request, Depends
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

db: Session


# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = SessionLocal()
    yield
    db.close()


lifespan = lifespan
app = FastAPI(lifespan=lifespan)


def handle_monitor_task(cursor: str):
    s1 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(s1)
    # s2 = datetime.fromtimestamp(1704277200000/1000).strftime('%Y-%m-%d %H:%M:%S')
    # print(s2)
    user = models.History()
    user.platform = 'wf'
    user.create_time = s1
    db.add(user)
    db.commit()
    db.refresh(user)


@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(None), cursor: str = Form()):
    background_tasks.add_task(handle_monitor_task, cursor)
    return {"message": "请求成功"}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
