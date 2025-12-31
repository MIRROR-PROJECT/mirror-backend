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
    current_user_id: str = Depends(get_current_user_id) # 💡 로그인 여부 확인
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


# 💡 AI 분석 전까지 데이터를 담아둘 임시 저장소
# key: user_id (str), value: style_answers 리스트
temp_quiz_store = {}

@router.post("/style-quiz", response_model=schemas.BaseResponse, status_code=status.HTTP_201_CREATED)
async def store_style_quiz(
    request: schemas.StyleQuizRequest,
    current_user_id: str = Depends(get_current_user) # 신분증 검사 및 ID 추출
    ):
    """
    [Step 2] 인지성향 질답 임시 저장 API
    """
    try:
        # 1. 메모리에 유저 ID별로 질답 리스트 저장
        # 이 데이터는 나중에 finalize API에서 꺼내어 AI 프롬프트로 들어갑니다.
        temp_quiz_store[str(request.user_id)] = request.style_answers
        
        # 2. 명세서 규격에 맞춘 성공 응답 (code 200 요청 반영)
        return schemas.BaseResponse.success_res(
            data=None,
            message="인지성향 답변 임시 저장 완료",
            code=200
        )
        
    except Exception as e:
        # 3. 실패 응답
        return schemas.BaseResponse.fail_res(
            message="유효하지 않은 유저 ID이거나 프로필 설정 단계가 올바르지 않습니다.",
            code=400
        )