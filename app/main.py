from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database
from .api import setup
from .api import routines
from .services import morphing
import os
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from .database import engine

# 서버 시작 시 테이블 재생성
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mirror AI Backend")

# --- [CORS 설정 시작] ---
# 허용할 프론트엔드 도메인 목록
origins = [
    "http://localhost:3000",          # 로컬 개발 환경 (React/Next.js)
    "https://mirror123.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],              # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"],              # 모든 HTTP 헤더 허용
)
# --- [CORS 설정 끝] ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return schemas.BaseResponse.success_res(message="Mirror AI Backend is running!")

# 라우터 등록
app.include_router(setup.router)
app.include_router(routines.router)
