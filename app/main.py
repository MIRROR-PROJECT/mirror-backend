from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models, database, schemas
from .api import setup, routines, my, onboarding, auth, studyroom

# --- 비동기 DB 초기화 함수 ---
async def init_db():
    async with database.engine.begin() as conn:
        # 개발 환경을 위해 시작 시 테이블 삭제 후 재생성
        # await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)

app = FastAPI(title="Mirror AI Backend")

@app.on_event("startup")
async def on_startup():
    print("서버 시작! 데이터베이스를 초기화합니다...")
    await init_db()
    print("데이터베이스 초기화 완료!")

# --- [CORS 설정] ---
origins = [
    "http://localhost:3000",
    "https://mirror123.vercel.app"
]

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
app.include_router(my.router)
app.include_router(onboarding.router)
app.include_router(auth.router) 
app.include_router(studyroom.router) 