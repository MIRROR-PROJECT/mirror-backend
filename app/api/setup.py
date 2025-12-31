from fastapi import APIRouter, Depends, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.dependencies import get_current_user
import uuid
from app.services.ai_service import analyze_solving_habit 

# 라우터 파일명을 반영하여 태그와 접두사 설정
router = APIRouter(prefix="/setup", tags=["Step 1: 초기 설정"])

@router.post("/basic-info", response_model=schemas.StudentProfileResponse, status_code=status.HTTP_201_CREATED)
def create_student_basic_info(
    request: schemas.ProfileCreateRequest, 
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user) # 💡 로그인 여부 확인
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
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [Step 3] 풀이 이미지 분석 API
    - Step 2에서 저장한 퀴즈 답변(temp_quiz_store)과 이미지를 함께 분석합니다.
    """
    
    # 1. Step 2 데이터 존재 여부 확인
    user_id_str = str(user_id)
    if user_id_str not in temp_quiz_store:
        return schemas.CommonResponse.fail_res(
            message="이전 단계의 퀴즈 데이터가 없습니다. Step 2를 먼저 완료해주세요.",
            code=400
        )
    
    style_answers = temp_quiz_store[user_id_str]

    try:
        # 2. 이미지 파일 읽기
        image_data = await file.read()

        # 3. AI 서비스 호출 (Llama 3.3 또는 Vision 모델 사용)
        # 💡 유저의 퀴즈 답변(style_answers)을 프롬프트에 녹여서 분석 정확도를 높입니다.
        analysis_result = await analyze_solving_habit(image_data, style_answers)

        # 4. DB 저장 (분석 결과 기록)
        # models.AnalysisLog가 정의되어 있다고 가정합니다.
        new_analysis = models.AnalysisLog(
            user_id=user_id,
            extracted_content=analysis_result["extracted_content"],
            detected_tags=analysis_result["detected_tags"]
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        # 5. 분석이 완료되었으므로 임시 저장소에서 삭제
        del temp_quiz_store[user_id_str]

        # 6. 명세서 규격에 따른 성공 응답
        return schemas.CommonResponse.success_res(
            message="이미지 분석 및 데이터 저장 완료",
            code=200,
            data={
                "analysis_id": new_analysis.id,
                "extracted_content": new_analysis.extracted_content,
                "detected_tags": new_analysis.detected_tags
            }
        )

    except Exception as e:
        db.rollback()
        return schemas.CommonResponse.fail_res(
            message=f"분석 중 오류 발생: {str(e)}",
            code=400
        )