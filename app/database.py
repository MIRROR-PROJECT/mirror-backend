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
engine = create_async_engine(ASYNC_DATABASE_URL)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

Base = declarative_base()

# 비동기 DB 세션 의존성 주입 함수
async def get_db() -> AsyncSession:
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()