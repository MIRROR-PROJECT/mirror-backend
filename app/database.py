from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# .env 로드
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Put it in .env or export it.")

# 비동기 드라이버를 사용하도록 DATABASE_URL 수정
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# 비동기 엔진 및 세션 설정
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,  # 연결 전 핑 테스트
    pool_size=5,  # 연결 풀 크기
    max_overflow=10,  # 최대 추가 연결
    pool_timeout=30,  # 연결 풀 대기 시간
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "timeout": 60,  # 연결 타임아웃 60초로 증가
        "command_timeout": 60  # 명령 실행 타임아웃
    }
)
# 세션 설정 수정
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False  # 이 부분을 반드시 추가하세요!
)

Base = declarative_base()

# 비동기 DB 세션 의존성 주입 함수
async def get_db() -> AsyncSession:
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()