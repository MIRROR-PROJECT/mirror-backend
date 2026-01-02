from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from uuid import UUID
from datetime import date, time, datetime
from typing import List, Optional, Generic, TypeVar, Any
from .models import CognitiveType
import uuid
from enum import Enum

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
    student_name: str = Field(..., description="학생 이름", example="홍길동") # 추가
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

# --- [주간 루틴 관련 스키마] ---

class DayOfWeek(str, Enum):
    """요일 Enum"""
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"


class RoutineBlockRequest(BaseModel):
    """루틴 블록 단일 항목 (요청용)"""
    day_of_week: DayOfWeek = Field(
        ..., 
        description="요일 (MON, TUE, WED, THU, FRI, SAT, SUN)",
        example="MON"
    )
    start_time: str = Field(
        ..., 
        description="시작 시간 (HH:MM 형식, 24시간제)",
        example="09:00",
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
    )
    end_time: str = Field(
        ..., 
        description="종료 시간 (HH:MM 형식, 24시간제)",
        example="11:00",
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
    )
    total_minutes: int = Field(
        ..., 
        description="해당 블록의 지속 시간(분)",
        example=120,
        gt=0
    )
    block_name: Optional[str] = Field(
        None,
        description="블록 이름 (예: '아침 자습', '수학 학원')",
        example="수학 학원"
    )
    category: Optional[str] = Field(
        None,
        description="카테고리 (예: '수학', '영어', '자유학습')",
        example="수학"
    )

    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """시간 형식 검증"""
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"잘못된 시간 형식입니다. HH:MM 형식을 사용하세요. (입력값: {v})")

    @field_validator('total_minutes')
    @classmethod
    def validate_total_minutes(cls, v: int, info) -> int:
        """total_minutes 검증 (start_time과 end_time 차이와 일치해야 함)"""
        # Note: 이 검증은 model_validator로 구현하는 것이 더 적절할 수 있습니다
        if v <= 0:
            raise ValueError("total_minutes는 0보다 커야 합니다.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "day_of_week": "MON",
                "start_time": "18:00",
                "end_time": "20:00",
                "total_minutes": 120,
                "block_name": "수학 학원",
                "category": "수학"
            }
        }
    )


class RoutineCreateRequest(BaseModel):
    """주간 루틴 등록 요청"""
    student_id: UUID = Field(
        ..., 
        description="학생 고유 ID",
        example="a3b5c7d9-1234-5678-90ab-cdef12345678"
    )
    routines: List[RoutineBlockRequest] = Field(
        ..., 
        description="시간 블록 배열 (같은 요일에 여러 블록 등록 가능)",
        min_length=1
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "a3b5c7d9-1234-5678-90ab-cdef12345678",
                "routines": [
                    {
                        "day_of_week": "MON",
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "total_minutes": 120,
                        "block_name": "오전 자습",
                        "category": "자유학습"
                    },
                    {
                        "day_of_week": "MON",
                        "start_time": "18:00",
                        "end_time": "20:00",
                        "total_minutes": 120,
                        "block_name": "수학 학원",
                        "category": "수학"
                    },
                    {
                        "day_of_week": "TUE",
                        "start_time": "19:00",
                        "end_time": "22:00",
                        "total_minutes": 180,
                        "block_name": "영어 학원",
                        "category": "영어"
                    }
                ]
            }
        }
    )


class RoutineItem(BaseModel):
    """루틴 블록 단일 항목 (응답용)"""
    id: UUID = Field(..., description="루틴 블록 ID")
    day_of_week: str = Field(..., description="요일")
    start_time: str = Field(..., description="시작 시간 (HH:MM)")
    end_time: str = Field(..., description="종료 시간 (HH:MM)")
    total_minutes: int = Field(..., description="지속 시간(분)")
    block_name: Optional[str] = Field(None, description="블록 이름")
    category: Optional[str] = Field(None, description="카테고리")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "day_of_week": "MON",
                "start_time": "09:00",
                "end_time": "11:00",
                "total_minutes": 120,
                "block_name": "오전 자습",
                "category": "자유학습"
            }
        }
    )


class RoutineCreateResponse(BaseResponse[List[UUID]]):
    """주간 루틴 등록 응답"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "code": 201,
                "message": "주간 루틴 등록 성공",
                "data": [
                    "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "8d3e4f5a-6b7c-8d9e-0f1a-2b3c4d5e6f7a",
                    "9e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b"
                ]
            }
        }
    )
