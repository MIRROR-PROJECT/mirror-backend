from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import datetime

from .database import get_db
from .models import WeeklyRoutine, StudentProfile
from .schemas import BaseResponse, RoutineCreateRequest

router = APIRouter(
    prefix="/routines",
    tags=["routines"]
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_weekly_routines(
    request: RoutineCreateRequest,
    db: Session = Depends(get_db)
):
    """주간 루틴 등록"""
    
    # 1. 학생 존재 여부 확인
    student = db.query(StudentProfile).filter(
        StudentProfile.id == request.student_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"학생 ID {request.student_id}를 찾을 수 없습니다."
        )
    
    # 2. 새로운 루틴 생성
    created_routine_ids = []
    
    try:
        for routine_data in request.routines:
            # 시간 문자열을 time 객체로 변환
            start_time = datetime.datetime.strptime(
                routine_data.start_time, "%H:%M"
            ).time()
            end_time = datetime.datetime.strptime(
                routine_data.end_time, "%H:%M"
            ).time()
            
            # WeeklyRoutine 객체 생성
            new_routine = WeeklyRoutine(
                student_id=request.student_id,
                day_of_week=routine_data.day_of_week,
                start_time=start_time,
                end_time=end_time,
                total_minutes=routine_data.total_minutes
            )
            
            db.add(new_routine)
            db.flush()
            created_routine_ids.append(new_routine.id)
        
        db.commit()
        
        return BaseResponse.success_res(
            data=created_routine_ids,
            message="주간 루틴 등록 성공",
            code=status.HTTP_201_CREATED
        )
        
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"시간 형식 오류: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"루틴 등록 중 오류 발생: {str(e)}"
        )