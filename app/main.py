from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database
from .api import setup
from .services import morphing
import os
from dotenv import load_dotenv
from google import genai
from openai import OpenAI

# 서버 시작 시 테이블 생성
models.Base.metadata.create_all(bind=database.engine)

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
# app.include_router(home.router) 

# # 1. .env 파일의 환경변수 로드
# load_dotenv()
# api_key = os.getenv("LLAMA_API_KEY")

# client = OpenAI(
#   base_url="https://openrouter.ai/api/v1",
#   api_key=api_key # 여기에 발급받은 키를 넣으세요
# )

# # 2. Llama 3.3 모델에게 대화 요청
# completion = client.chat.completions.create(
#   model="meta-llama/llama-3.3-70b-instruct:free",
  
#   messages=[
#     {
#       "role": "system",
#       # Llama는 기본적으로 영어를 쓰려 하므로, 한국어 설정을 꼭 해주는 게 좋습니다.
#       "content": "너는 한국어를 아주 자연스럽게 구사하는 AI 친구야. 번역투 쓰지 말고 편안하게 대화해 줘."
#     },
#     {
#       "role": "user",
#       "content": "요즘 대학생들이 가장 고민하는 게 뭘까? 진지하게 이야기 좀 해보자."
#     }
#   ],
# )

# # 3. 답변 출력
# print(completion.choices[0].message.content)