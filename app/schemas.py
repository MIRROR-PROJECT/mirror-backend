from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import date, time, datetime
from typing import List, Optional
from .models import CognitiveType

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