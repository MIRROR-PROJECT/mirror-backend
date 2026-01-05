from fastapi import APIRouter, Depends, status, File, UploadFile, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
async def create_student_basic_info(
    request: schemas.ProfileCreateRequest, 
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [Step 1] 학생 기본 정보 등록
    - 입력받은 student_name으로 유저 정보를 업데이트하거나 생성합니다.
    """
    
    # 1. User 테이블 확인
    result = await db.execute(select(models.User).filter(models.User.id == request.user_id))
    user = result.scalars().first()
    
    if not user:
        user = models.User(
            id=request.user_id,
            email=f"user_{str(request.user_id)[:8]}@example.com",
            name=request.student_name,
            role="student"
        )
        db.add(user)
    else:
        user.name = request.student_name

    try:
        await db.flush()
    except Exception as e:
        await db.rollback()
        return schemas.StudentProfileResponse.fail_res(message="유저 정보 처리 실패", code=500)

    # 2. 프로필 중복 체크
    result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == request.user_id))
    existing_profile = result.scalars().first()
    
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
        await db.commit()
        await db.refresh(new_profile)

        return schemas.StudentProfileResponse.success_res(
            data=schemas.ProfileResponseData.from_orm(new_profile),
            message="학생 등록 및 프로필 생성 완료",
            code=201
        )

    except Exception as e:
        await db.rollback()
        return schemas.StudentProfileResponse.fail_res(message=f"저장 오류: {str(e)}", code=500)


@router.post("/style-quiz", response_model=schemas.BaseResponse)
async def store_style_quiz(
    request: schemas.StyleQuizRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    result = await db.execute(
        select(models.StudentProfile).filter(models.StudentProfile.user_id == str(request.user_id))
    )
    profile = result.scalars().first()
    
    if not profile:
        return schemas.BaseResponse.fail_res(message="프로필이 존재하지 않습니다.", code=400)

    profile.cognitive_type = request.cognitive_type
    await db.commit()
    
    return schemas.BaseResponse.success_res(message="인지성향 답변 저장 완료", code=200)

@router.post("/solving-image", response_model=schemas.AnalysisResponse)
async def analyze_solving_image(
    user_id: uuid.UUID = Form(...),
    files: List[UploadFile] = File(...),
    subjects: List[str] = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    # 1. 학생 프로필 조회
    result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == user_id))
    profile = result.scalars().first()
    
    if not profile:
        return schemas.AnalysisResponse.fail_res(
            message="프로필이 없습니다.", 
            code=400
        )

    analysis_results = []

    for i, file in enumerate(files):
        try:
            image_data = await file.read()
            target_subject = subjects[i] if i < len(subjects) else "ETC"
            
            analysis = await analyze_solving_habit(
                image_data, 
                profile.cognitive_type, 
                target_subject
            )
            
            new_log = models.DiagnosisLog(
                student_id=profile.id,
                subject=target_subject,
                solution_habit_summary=analysis.get("extracted_content"),
                detected_tags=analysis.get("detected_tags", []),
            )
            db.add(new_log)
            await db.flush()

            analysis_results.append({
                "analysis_id": str(new_log.id),
                "subject": target_subject,
                "extracted_content": new_log.solution_habit_summary,
                "detected_tags": new_log.detected_tags
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            continue

    await db.commit()

    return schemas.AnalysisResponse.success_res(
        data=analysis_results,
        message=f"{len(analysis_results)}개 과목 분석 및 저장 완료",
        code=201
    )