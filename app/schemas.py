from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from datetime import date, time, datetime
from typing import List, Optional, Generic, TypeVar, Any
from .models import CognitiveType
import uuid

# --- [추가] 공통 응답 규격 ---
T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    success: bool
    code: int
    message: str
    data: Optional[T] = None

    @classmethod
    def success_res(cls, data: Any = None, message: str = "요청 처리 성공", code: int = 200):
        return cls(success=True, code=code, message=message, data=data)

    @classmethod
    def fail_res(cls, message: str = "요청 처리 실패", code: int = 400):
        return cls(success=False, code=code, message=message, data=None)

# --- [데이터 상세 모델] ---
class ProfileResponseData(BaseModel):
    profile_id: UUID = Field(validation_alias="id") # DB의 'id'를 'profile_id'로 읽어옴
    user_id: UUID
    streak_days: int = 0
    total_points: int = 0

    class Config:
        from_attributes = True # SQLAlchemy 모델 객체를 Pydantic으로 자동 변환

# --- [요청 모델] ---
class ProfileCreateRequest(BaseModel):
    user_id: UUID
    school_grade: int
    semester: int
    subjects: List[str]

class StyleQuizRequest(BaseModel):
    user_id: uuid.UUID
    cognitive_type: CognitiveType

# --- [응답 모델] ---
class StudentProfileResponse(BaseResponse[ProfileResponseData]):
    """Step 1 응답: 프로필 데이터 포함"""
    pass

class CommonResponse(BaseResponse[Any]):
    """Step 3 응답: 분석 결과 등 가변 데이터 포함"""
    pass

class AnalysisResultItem(BaseModel):
    analysis_id: UUID
    subject: str
    extracted_content: str
    detected_tags: List[str]

    model_config = ConfigDict(from_attributes=True)

# data: List[AnalysisResultItem] 구조가 됨
class CommonResponse(BaseResponse[List[AnalysisResultItem]]):
    pass