from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 환경 변수 확인
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"연결 시도 중: {DATABASE_URL}")

try:
    # 1. 엔진 생성
    engine = create_engine(DATABASE_URL)
    
    # 2. 연결 시도 및 쿼리 실행
    with engine.connect() as connection:
        # SELECT 1 쿼리를 실행하여 연결 확인
        result = connection.execute(text("SELECT 1"))
        print("✅ DB 연결 성공!")
        print(f"쿼리 결과: {result.fetchone()[0]}")
        
except Exception as e:
    print("❌ DB 연결 실패!")
    print(f"에러 내용: {e}")