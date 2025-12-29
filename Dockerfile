# 1. 베이스 이미지 설정
FROM python:3.11-slim

# 2. 작업 디렉토리 생성
WORKDIR /app

# 3. 필수 도구 설치 (PostgreSQL 연결 등을 위해 필요한 경우)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 포트 설정 (FastAPI 기본 포트 8000)
EXPOSE 8000

# 7. 실행 명령어 (uvicorn 사용)
# --proxy-headers: 로드밸런서(Render 등)를 사용할 때 클라이언트 IP를 정확히 잡기 위해 필요
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]