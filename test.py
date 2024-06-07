from contextlib import asynccontextmanager

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
    user = models.History()
    user.platform = 'wf'
    db.add(user)
    db.commit()
    db.refresh(user)
    print(user)


@app.post("/")
async def root(background_tasks: BackgroundTasks, link: str = Form(None), cursor: str = Form()):
    background_tasks.add_task(handle_monitor_task, cursor)
    return {"message": "请求成功"}


if __name__ == '__main__':
    uvicorn.run("test:app", host="0.0.0.0", port=8000, reload=True)
