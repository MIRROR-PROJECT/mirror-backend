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
# def create_student_basic_info(
#     request: schemas.ProfileCreateRequest, 
#     db: Session = Depends(get_db),
#     current_user_id: str = Depends(get_current_user) # 💡 로그인 여부 확인
# ):
#     """
#     [Step 1] 학생 기본 정보 등록
#     - 학년, 학기, 과목 정보를 받아 초기 프로필을 생성합니다.
#     """
#     # 1. 중복 체크
#     existing_profile = db.query(models.StudentProfile).filter(
#         models.StudentProfile.user_id == request.user_id
#     ).first()
    
#     if existing_profile:
#         return schemas.StudentProfileResponse.fail_res(
#             message="해당 유저에 대한 프로필이 이미 존재합니다.",
#             code=400
#         )

#     # 2. 프로필 생성 (기본값으로 시작)
#     new_profile = models.StudentProfile(
#         user_id=request.user_id,
#         school_grade=request.school_grade,
#         semester=request.semester,
#         subjects=request.subjects
#     )
    
#     db.add(new_profile)
#     db.commit()
#     db.refresh(new_profile)
def create_student_basic_info(
    request: schemas.ProfileCreateRequest, 
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [Step 1] 학생 기본 정보 등록
    - 유저가 없으면 생성하고, 프로필을 연결합니다.
    """
    
    # 1. [핵심] User 테이블에 해당 유저가 있는지 확인 및 강제 생성
    # 수파베이스 로그인은 성공했지만 우리 DB에 없을 경우를 대비합니다.
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    
    if not user:
        # 유저가 없으면 새로 생성 (부모 레코드 생성)
        # email과 name은 request에 포함시키거나 토큰에서 가져와야 합니다.
        new_user = models.User(
            id=request.user_id,
            email=getattr(request, 'email', f"user_{str(request.user_id)[:8]}@example.com"), # 임시 이메일 처리
            name=getattr(request, 'name', "신규학생"),
            role="STUDENT"
        )
        db.add(new_user)
        try:
            db.flush() # Commit 전 단계에서 ID를 DB에 등록 (외래 키 연결용)
        except Exception as e:
            db.rollback()
            return schemas.StudentProfileResponse.fail_res(
                message=f"유저 레코드 생성 실패: {str(e)}",
                code=500
            )

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
            # 모델 정의에 따라 기본값들 설정
            streak_days=0,
            total_points=0
        )
        
        db.add(new_profile)
        db.commit() # 부모(User)와 자식(Profile)이 동시에 영구 저장됨
        db.refresh(new_profile)

        return schemas.StudentProfileResponse.success_res(
            data=schemas.ProfileResponseData.from_orm(new_profile),
            message="유저 및 프로필 등록 완료",
            code=201
        )

    except Exception as e:
        db.rollback()
        return schemas.StudentProfileResponse.fail_res(
            message=f"데이터 저장 중 오류 발생: {str(e)}",
            code=500
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