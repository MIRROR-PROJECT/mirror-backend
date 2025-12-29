from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from .. import models, schemas, database
from datetime import datetime
from typing import List
from uuid import UUID

router = APIRouter(prefix="/setup", tags=["Setup"]) # 노션의 Setup 페이지 그룹

# 학생 프로필 설정
@router.post(
    "/student", 
    response_model=schemas.BaseResponse[dict], 
    status_code=status.HTTP_201_CREATED
)
def create_student_profile(
    profile_data: schemas.StudentProfileCreate, 
    db: Session = Depends(database.get_db)
):
    """
    [POST] 학생 프로필 최초 설정
    - 특정 유저의 학년, 학기, 과목, 인지 유형을 등록합니다.
    - 이미 프로필이 존재하는 경우 400 에러를 반환합니다.
    """
    
    # 1. 이미 해당 유저의 프로필이 존재하는지 확인
    existing_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == profile_data.user_id
    ).first()
    
    if existing_profile:
        return schemas.BaseResponse.fail_res(
            message="해당 유저에 대한 프로필이 이미 존재합니다.",
            code=status.HTTP_400_BAD_REQUEST
        )

    # 2. 새로운 프로필 객체 생성
    new_profile = models.StudentProfile(
        user_id=profile_data.user_id,
        school_grade=profile_data.school_grade,
        semester=profile_data.semester,
        subjects=profile_data.subjects,
        cognitive_type=profile_data.cognitive_type,
        streak_days=0,
        total_points=0
    )

    # 3. DB 저장 및 반영
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    # 4. 명세서 상세 규격에 맞춘 데이터 구성
    result = {
        "profile_id": new_profile.id,
        "user_id": new_profile.user_id,
        "streak_days": new_profile.streak_days,
        "total_points": new_profile.total_points
    }

    return schemas.BaseResponse.success_res(
        data=result,
        message="학생 프로필 설정 성공",
        code=status.HTTP_201_CREATED
    )


# 주간 루틴 등록
@router.post(
    "/routines", 
    response_model=schemas.BaseResponse[List[UUID]], 
    status_code=status.HTTP_201_CREATED
)
def create_weekly_routines(
    data: schemas.WeeklyRoutineBulkCreate, 
    db: Session = Depends(database.get_db)
):
    """
    [POST] 주간 루틴 대량 등록
    - 요일별 가용 시간을 리스트로 받아 한 번에 저장합니다.
    """
    
    # 1. 학생 존재 여부 확인
    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.id == data.student_id
    ).first()
    
    if not student:
        return schemas.BaseResponse.fail_res(
            message="해당 학생 프로필을 찾을 수 없습니다.",
            code=status.HTTP_404_NOT_FOUND
        )

    created_ids = []
    try:
        # 2. 루틴 리스트 순회하며 객체 생성
        for item in data.routines:
            # 문자열 시간을 time 객체로 변환 (HH:MM -> time)
            try:
                start_t = datetime.strptime(item.start_time, "%H:%M").time()
                end_t = datetime.strptime(item.end_time, "%H:%M").time()
            except ValueError:
                return schemas.BaseResponse.fail_res(
                    message="시간 형식이 올바르지 않습니다. (HH:MM 권장)",
                    code=status.HTTP_400_BAD_REQUEST
                )

            new_routine = models.WeeklyRoutine(
                student_id=data.student_id,
                day_of_week=item.day_of_week,
                start_time=start_t,
                end_time=end_t,
                total_minutes=item.total_minutes
            )
            db.add(new_routine)
            db.flush()  # ID 생성을 위해 flush 실행
            created_ids.append(new_routine.id)

        # 3. 전체 저장 반영
        db.commit()
        
    except Exception as e:
        db.rollback()
        return schemas.BaseResponse.fail_res(
            message=f"루틴 등록 중 오류 발생: {str(e)}",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return schemas.BaseResponse.success_res(
        data=created_ids,
        message="주간 루틴 등록 성공",
        code=status.HTTP_201_CREATED
    )


# 시험기간 일정 등록
@router.post("/exam_routines", response_model=schemas.BaseResponse[dict], status_code=status.HTTP_201_CREATED)
def create_exam_routine(data: schemas.ExamRoutineBulkCreate, db: Session = Depends(database.get_db)):
    # 1. 날짜 유효성 체크
    if data.start_date > data.end_date:
        return schemas.BaseResponse.fail_res(message="종료일이 시작일보다 빠를 수 없습니다.")

    # 2. 시험 마스터 정보 저장 (ExamPeriod)
    new_exam = models.ExamPeriod(
        student_id=data.student_id,
        title=data.title,
        start_date=data.start_date,
        end_date=data.end_date
    )
    db.add(new_exam)
    db.flush()

    # 3. 시험 기간 전용 요일별 상세 루틴 저장 (ExamDayRoutine)
    # 이 과정에서 드래그로 설정한 각 요일의 개별 항목들이 DB에 보존됩니다.
    for item in data.routines:
        detail = models.ExamDayRoutine(
            exam_period_id=new_exam.id,
            day_of_week=item.day_of_week,
            start_time=datetime.strptime(item.start_time, "%H:%M").time(),
            end_time=datetime.strptime(item.end_time, "%H:%M").time(),
            total_minutes=item.total_minutes
        )
        db.add(detail)

    db.commit()

    return schemas.BaseResponse.success_res(
        data={
            "exam_routine_id": new_exam.id,
            "d_day": (data.start_date - date.today()).days,
            "total_days": (data.end_date - data.start_date).days + 1
        },
        message="요일별 상세 시험 루틴이 저장되었습니다."
    )