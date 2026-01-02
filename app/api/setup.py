from fastapi import APIRouter, Depends, status, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.services.ai_service import analyze_solving_habit 
import uuid
import requests
import os

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user

# 라우터 파일명을 반영하여 태그와 접두사 설정
router = APIRouter(prefix="/setup", tags=["Step 1: 초기 설정"])

@router.post("/basic-info", response_model=schemas.StudentProfileResponse, status_code=status.HTTP_201_CREATED)
def create_student_basic_info(
    request: schemas.ProfileCreateRequest, 
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [Step 1] 학생 기본 정보 등록
    - 입력받은 student_name으로 유저 정보를 업데이트하거나 생성합니다.
    """
    
    # 1. User 테이블 확인
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    
    if not user:
        # 유저가 없으면 새로 생성
        user = models.User(
            id=request.user_id,
            email=f"user_{str(request.user_id)[:8]}@example.com", # 실제 환경에선 토큰 등에서 추출 권장
            name=request.student_name, # 프론트에서 받은 이름 저장
            role="STUDENT"
        )
        db.add(user)
    else:
        # 유저가 이미 있다면 이름을 프론트에서 받은 이름으로 동기화(업데이트)
        user.name = request.student_name

    try:
        db.flush() # ID 확정 및 유저 정보 반영
    except Exception as e:
        db.rollback()
        return schemas.StudentProfileResponse.fail_res(message="유저 정보 처리 실패", code=500)

    # 2. 프로필 중복 체크
    existing_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == request.user_id
    ).first()
    
    if existing_profile:
        return schemas.StudentProfileResponse.fail_res(
            message="해당 유저에 대한 프로필이 이미 존재합니다.",
            code=400
        )

    # 3. 프로필 생성
    try:
        new_profile = models.StudentProfile(
            user_id=request.user_id,
            school_grade=request.school_grade,
            semester=request.semester,
            subjects=request.subjects,
            streak_days=0,
            total_points=0
        )
        
        db.add(new_profile)
        db.commit() 
        db.refresh(new_profile)

        return schemas.StudentProfileResponse.success_res(
            data=schemas.ProfileResponseData.from_orm(new_profile),
            message="학생 등록 및 프로필 생성 완료",
            code=201
        )

    except Exception as e:
        db.rollback()
        return schemas.StudentProfileResponse.fail_res(message=f"저장 오류: {str(e)}", code=500)


@router.post("/style-quiz", response_model=schemas.BaseResponse)
async def store_style_quiz(
    request: schemas.StyleQuizRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == str(request.user_id)
    ).first()
    
    if not profile:
        return schemas.BaseResponse.fail_res(message="프로필이 존재하지 않습니다.", code=400)

    profile.cognitive_type = request.cognitive_type # Enum 저장
    db.commit()
    
    return schemas.BaseResponse.success_res(message="인지성향 답변 저장 완료", code=200)

@router.post("/solving-image", response_model=schemas.CommonResponse)
async def analyze_solving_image(
    user_id: uuid.UUID = Form(...),
    files: List[UploadFile] = File(...),
    subjects: List[str] = Form(...), # ["KOREAN", "MATH"] 형태
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    # 1. 유저 성향(Step 2 결과) 조회
    profile = db.query(models.StudentProfile).filter(models.StudentProfile.user_id == user_id).first()
    if not profile:
        return schemas.CommonResponse.fail_res(message="프로필이 없습니다.", code=400)

    analysis_results = []

    try:
        # 2. 전송된 파일 리스트 루프 실행
        for i, file in enumerate(files):
            image_data = await file.read()
            # 파일 순서에 맞는 과목명 매칭 (없으면 UNKNOWN)
            target_subject = subjects[i] if i < len(subjects) else "UNKNOWN"

            # 3. AI 서비스 호출
            analysis = await analyze_solving_habit(
                image_data, 
                profile.cognitive_type, 
                target_subject
            )

            # 4. 개별 결과 DB 저장
            new_log = models.AnalysisLog(
                user_id=user_id,
                subject=target_subject,
                extracted_content=analysis.get("extracted_content"),
                detected_tags=analysis.get("detected_tags")
            )
            db.add(new_log)
            db.flush() # ID 생성을 위해 flush

            # 5. 응답용 리스트에 담기
            analysis_results.append({
                "analysis_id": new_log.id,
                "subject": target_subject,
                "extracted_content": new_log.extracted_content,
                "detected_tags": new_log.detected_tags
            })

        db.commit()
        
        # 6. 최종 명세에 맞춰 List[Object] 형태로 반환
        return schemas.CommonResponse.success_res(
            data=analysis_results,
            message="각 과목 분석 및 데이터 저장 완료",
            code=201
        )

    except Exception as e:
        db.rollback()
        return schemas.CommonResponse.fail_res(message=f"오류 발생: {str(e)}", code=500)