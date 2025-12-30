from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

# 라우터 파일명을 반영하여 태그와 접두사 설정
router = APIRouter(prefix="/setup", tags=["Step 1: 초기 설정"])

@router.post("/basic-info", response_model=schemas.StudentProfileResponse, status_code=status.HTTP_201_CREATED)
def create_student_basic_info(
    request: schemas.ProfileCreateRequest, 
    db: Session = Depends(get_db)
):
    """
    [Step 1] 학생 기본 정보 등록
    - 학년, 학기, 과목 정보를 받아 초기 프로필을 생성합니다.
    """
    # 1. 중복 체크
    existing_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == request.user_id
    ).first()
    
    if existing_profile:
        return schemas.StudentProfileResponse.fail_res(
            message="해당 유저에 대한 프로필이 이미 존재합니다.",
            code=400
        )

    # 2. 프로필 생성 (기본값으로 시작)
    new_profile = models.StudentProfile(
        user_id=request.user_id,
        school_grade=request.school_grade,
        semester=request.semester,
        subjects=request.subjects
    )
    
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    # 3. 공통 응답 규격에 맞춰 반환
    return schemas.StudentProfileResponse.success_res(
        data=schemas.ProfileResponseData.from_orm(new_profile),
        message="기본 정보 등록 완료",
        code=201
    )