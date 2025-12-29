from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 실제 PostgreSQL 접속 정보를 입력하세요
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/mirror-db"
# SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mirror_db")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# DB 세션 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()