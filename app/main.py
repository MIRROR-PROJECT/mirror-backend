from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database
from .api import setup
from .services import morphing

# 서버 시작 시 테이블 생성
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Mirror AI Backend")

@app.get("/")
def root():
    return schemas.BaseResponse.success_res(message="Mirror AI Backend is running!")

from fastapi import FastAPI, Depends, status
from sqlalchemy.orm import Session
from . import models, schemas, database

# 라우터 등록
app.include_router(setup.router)
# app.include_router(home.router) 