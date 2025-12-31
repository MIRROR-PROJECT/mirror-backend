from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from datetime import date, time, datetime
from typing import List, Optional, Generic, TypeVar, Any
from .models import CognitiveType

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

# --- [최종 응답 모델] ---
# BaseResponse[ProfileResponseData] 형태로 제네릭을 활용합니다.
class StudentProfileResponse(BaseResponse[ProfileResponseData]):
    pass

# 질답 페어 개별 아이템
class StyleAnswerItem(BaseModel):
    question: str
    answer: str

# 2단계 요청 바디
class StyleQuizRequest(BaseModel):
    user_id: UUID
    style_answers: List[StyleAnswerItem]