from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/time-slots", response_model=schemas.TimeSlotResponse)
def get_student_time_slots(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    학생의 주간 가용 시간 가이드 조회
    - WeeklyRoutine 테이블에서 요일별 루틴을 조회하여 권장 학습 시간을 계산합니다.
    """

    # current_user_id를 student_id로 사용
    student_id = current_user_id
    
    # 1. 학생 프로필 존재 확인
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.id == student_id
    ).first()
    
    if not profile:
        return schemas.TimeSlotResponse.fail_res(
            message="해당 학생을 찾을 수 없습니다.",
            code=404
        )
    
    # 2. 주간 루틴 조회
    routines = db.query(models.WeeklyRoutine).filter(
        models.WeeklyRoutine.student_id == student_id
    ).all()
    
    # 3. 요일별로 그룹화하여 총 시간 계산
    day_order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    day_totals = {day: 0 for day in day_order}
    
    for routine in routines:
        # day_of_week가 "MON", "TUE" 형식이면 변환 필요
        day_map = {
            "MON": "MONDAY",
            "TUE": "TUESDAY", 
            "WED": "WEDNESDAY",
            "THU": "THURSDAY",
            "FRI": "FRIDAY",
            "SAT": "SATURDAY",
            "SUN": "SUNDAY"
        }
        
        # 이미 MONDAY 형식이면 그대로, MON 형식이면 변환
        day_key = day_map.get(routine.day_of_week, routine.day_of_week)
        
        if day_key in day_totals and routine.total_minutes:
            day_totals[day_key] += routine.total_minutes
    
    # 4. 응답 데이터 생성
    weekly_schedule = [
        schemas.DaySchedule(
            day_of_week=day,
            recommended_minutes=day_totals[day],
            source_type="ROUTINE"
        )
        for day in day_order
    ]
    
    return schemas.TimeSlotResponse.success_res(
        data=schemas.WeeklyScheduleData(weekly_schedule=weekly_schedule),
        message="주간 가용 시간 가이드 조회 성공",
        code=200
    )