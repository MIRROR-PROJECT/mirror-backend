from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas, database
from .services import morphing

app = FastAPI(title="Mirror AI Backend")

# 서버 시작 시 테이블 생성 (초기 단계용)
models.Base.metadata.create_all(bind=database.engine)

@app.post("/plans/generate")
def generate_student_plan(
    student_id: str, 
    available_time: int, 
    db: Session = Depends(database.get_db)
):
    # 1. 학생 성향 조회 (DB에서 가져온다고 가정, 여기선 임시로 DIVER 설정)
    # student = db.query(models.StudentProfile).filter(...)
    user_type = "DIVER" 
    
    # 2. Morphing 로직 실행
    morphed_tasks = morphing.apply_morphing_logic(available_time, user_type)
    
    # 3. 결과 반환 (이후 DB 저장 로직 추가 가능)
    return {
        "student_id": student_id,
        "type": user_type,
        "total_time": available_time,
        "schedule": morphed_tasks
    }