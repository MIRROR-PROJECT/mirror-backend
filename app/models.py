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
class StudentClassMatch(Base):
    __tablename__ = "student_class_matches"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 추가된 핵심 필드
    academy_name = Column(String, nullable=True)     # 학원 이름
    class_name = Column(String, nullable=False)       # 구체적인 반 이름 (예: "고2 수학 A반", "심화 물리반")
    class_code = Column(String, nullable=True)        # 반 고유 코드 (선택사항, 출석부 연동용)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="class_matches")
    teacher = relationship("User") # 강사 유저 정보와 연결

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

    # AI가 업데이트할 동적 필드들
    mastery_map = Column(JSONB, default={})        # {"수학": "중", "영어": "상"}
    error_patterns = Column(JSONB, default=[])     # ["계산실수", "개념혼동"]
    interaction_style = Column(String, nullable=True) # "핵심요약형", "상세설명형"
    
    # 통계
    streak_days = Column(Integer, default=0)
    total_points = Column(Integer, default=0)

    # 관계 설정 (N:M 연결 테이블을 통해 강사들과 연결됨)
    user = relationship("User", foreign_keys=[user_id])
    teacher_matches = relationship("StudentTeacherMatch", back_populates="student")
    weekly_routines = relationship("WeeklyRoutine", back_populates="student", cascade="all, delete-orphan")
    analysis_logs = relationship("ProblemAnalysisLog", back_populates="student")
    chat_messages = relationship("ChatMessage", back_populates="student")

# 5. 주간 루틴
class WeeklyRoutine(Base):
    __tablename__ = "weekly_routines"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    
    # 요일 정보 (Enum이나 String)
    day_of_week = Column(String, nullable=False) # "MON", "TUE" 등
    
    # 개별 블록 정보 - 각 블록의 이름을 명시 (예: "아침 자습", "수학 학원")
    block_name = Column(String, nullable=True) 
    start_time = Column(Time, nullable=False)  # 08:00
    end_time = Column(Time, nullable=False)    # 09:30
    
    # 3. 메타데이터 (RAG 분석용)
    category = Column(String, nullable=True)   # "수학", "영어", "자유학습"

    total_minutes = Column(Integer) 
    student = relationship("StudentProfile", back_populates="weekly_routines")


# 6. 일일 계획
class DailyPlan(Base):
    __tablename__ = "daily_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    plan_date = Column(Date, default=datetime.date.today)
    title = Column(String) # 해당 날짜 계획의 대표 명칭 (예: "기말고사 대비 수학 집중일")
    target_minutes = Column(Integer) # 그날 목표로 하는 순공 시간
    is_completed = Column(Boolean, default=False) 
    
    tasks = relationship("Task", back_populates="plan", cascade="all, delete-orphan")

# 7. 체크리스트 내의 개별 테스크
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

# 10. 문제 분석 결과
class ProblemAnalysisLog(Base):
    __tablename__ = "problem_analysis_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    
    # 분석 데이터
    source_type = Column(String)  # "DIAGNOSIS" (초기 진단) 또는 "STUDY" (일반 학습)
    extracted_text = Column(Text) # OCR로 추출된 문제 지문
    detected_concepts = Column(JSONB) # 문제에 포함된 개념 ["로그함수", "방정식"]
    difficulty_level = Column(String) # AI 판단 난이도 (상, 중, 하)
    
    # 학생 상태 판정
    error_reason = Column(String) # AI가 분석한 오답 원인
    ai_feedback_summary = Column(Text) # 해당 문제에 대한 AI의 핵심 코멘트
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="analysis_logs")
    chat_messages = relationship("ChatMessage", back_populates="problem_log")

11. 대화 맥락 저장
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    
    # 특정 문제에 대한 대화인 경우 연결 (FK)
    problem_log_id = Column(UUID(as_uuid=True), ForeignKey("problem_analysis_logs.id"), nullable=True)
    
    role = Column(String)    # "user" (학생) 또는 "assistant" (AI 튜터)
    content = Column(Text)   # 메시지 본문
    
    # AI가 분석한 대화 시점의 학생 상태 (부가 정보)
    student_sentiment = Column(String, nullable=True) # "이해함", "혼란스러움" 등
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="chat_messages")
    problem_log = relationship("ProblemAnalysisLog", back_populates="chat_messages")ㄴ