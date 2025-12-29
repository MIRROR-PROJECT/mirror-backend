from pydantic import BaseModel, EmailStr
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

# --- 기존 데이터 모델 ---

# 유저 생성용
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: UUID
    class Config:
        from_attributes = True

# 학생 프로필용
class StudentProfileBase(BaseModel):
    school_grade: int
    semester: int
    subjects: List[str]
    cognitive_type: CognitiveType

class StudentProfileCreate(StudentProfileBase):
    user_id: UUID

class StudentProfile(StudentProfileBase):
    id: UUID
    streak_days: int
    total_points: int
    class Config:
        from_attributes = True

# 태스크(체크리스트)용
class TaskBase(BaseModel):
    category: str
    title: str
    assigned_minutes: int
    sequence: int

class Task(TaskBase):
    id: UUID
    is_completed: bool
    class Config:
        from_attributes = True

# 일일 계획용
class DailyPlanBase(BaseModel):
    title: str
    target_minutes: int

class DailyPlan(DailyPlanBase):
    id: UUID
    plan_date: date
    is_completed: bool
    tasks: List[Task] = []
    class Config:
        from_attributes = True
        

# 주간 루틴 개별 항목
class WeeklyRoutineItem(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str
    total_minutes: int

# 주간 루틴 대량 등록 요청 바디
class WeeklyRoutineBulkCreate(BaseModel):
    student_id: UUID
    routines: List[WeeklyRoutineItem]

# 시험 기간 내 요일별 상세 시간 (주간 루틴과 동일한 구조)
class ExamDayRoutineItem(BaseModel):
    day_of_week: str  # MON, TUE ...
    start_time: str   # "14:00"
    end_time: str     # "18:00"
    total_minutes: int # 240

# 시험 루틴 생성 요청 (상세 항목 리스트 포함)
class ExamRoutineBulkCreate(BaseModel):
    student_id: UUID
    title: str
    start_date: date
    end_date: date
    routines: List[WeeklyRoutineItem]  # 요일별 상세 루틴 리스트 포함