import enum
import uuid
import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Date, Enum, Time
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .database import Base

# 1. 인지 유형
class CognitiveType(str, enum.Enum):
    SPEED_FIRST = "SPEED_FIRST"
    PRECISION_FIRST = "PRECISION_FIRST"
    BURST_STUDY = "BURST_STUDY"

# 2. 유저 정보
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="STUDENT") # "STUDENT", "TEACHER", "PARENT"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 3. 학생-강사 다중 매칭 연결 테이블 (N:M 관계 해결)
class StudentTeacherMatch(Base):
    __tablename__ = "student_teacher_matches"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    academy_name = Column(String, nullable=True) # 어떤 학원 소속으로 매칭되었는지 기록
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="teacher_matches")
    teacher = relationship("User")

# 4. 학생 프로필
class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # 기본 정보
    school_grade = Column(Integer)
    semester = Column(Integer)
    subjects = Column(JSONB)
    cognitive_type = Column(Enum(CognitiveType), default=CognitiveType.SPEED_FIRST)
    
    # 통계
    streak_days = Column(Integer, default=0)
    total_points = Column(Integer, default=0)

    # 관계 설정 (N:M 연결 테이블을 통해 강사들과 연결됨)
    user = relationship("User", foreign_keys=[user_id])
    teacher_matches = relationship("StudentTeacherMatch", back_populates="student")

# 5. 주간 루틴
class WeeklyRoutine(Base):
    __tablename__ = "weekly_routines"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    day_of_week = Column(String)
    start_time = Column(Time)
    end_time = Column(Time)
    total_minutes = Column(Integer)

# 6. 시험 대비 기간
class ExamPeriod(Base):
    __tablename__ = "exam_periods"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    title = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    daily_target_minutes = Column(Integer)

# 7. 일일 계획
class DailyPlan(Base):
    __tablename__ = "daily_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    plan_date = Column(Date, default=datetime.date.today)
    title = Column(String)
    target_minutes = Column(Integer)
    source_type = Column(String)
    is_completed = Column(Boolean, default=False)
    
    tasks = relationship("Task", back_populates="plan", cascade="all, delete-orphan")

# 8. 체크리스트 태스크
class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id"))
    category = Column(String)
    title = Column(String)
    assigned_minutes = Column(Integer)
    is_completed = Column(Boolean, default=False)
    sequence = Column(Integer)
    
    plan = relationship("DailyPlan", back_populates="tasks")

# 9. 학습 분석 (성취도)
class LearningAnalytics(Base):
    __tablename__ = "learning_analytics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    subject_name = Column(String)
    unit_name = Column(String)
    achievement_rate = Column(Float)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)