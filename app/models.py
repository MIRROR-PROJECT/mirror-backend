import enum
import uuid
from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Date, Enum, Time, Text, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
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
    phone_number = Column(String, nullable=True)  # "010-1234-5678"
    created_at = Column(DateTime, default=datetime.now)

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
    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="class_matches")
    teacher = relationship("User") # 강사 유저 정보와 연결

# 4-1. 학생 프로필
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
    class_matches = relationship("StudentClassMatch", back_populates="student")
    weekly_routines = relationship("WeeklyRoutine", back_populates="student", cascade="all, delete-orphan")
    daily_plans = relationship("DailyPlan", back_populates="student", cascade="all, delete-orphan")  
    diagnosis_logs = relationship("DiagnosisLog", back_populates="student", cascade="all, delete-orphan")
    problem_logs = relationship("ProblemAnalysisLog", back_populates="student", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="student")
    analytics = relationship("LearningAnalytics", back_populates="student", cascade="all, delete-orphan")

# 4-2. Teacher (선생님 프로필)
class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # 선생님 기본 정보
    teacher_name = Column(String, nullable=True)
    subject_specialization = Column(JSONB, default=[])  # ["수학", "과학"] 전문 과목
    academy_name = Column(String, nullable=True)  # 소속 학원
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 관계
    user = relationship("User", foreign_keys=[user_id])
    # 향후 추가 가능: 담당 학생 목록 등


# 4-3. Parent (학부모 프로필)  
class ParentProfile(Base):
    __tablename__ = "parent_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # 학부모 기본 정보
    parent_name = Column(String, nullable=True)
    children_ids = Column(JSONB, default=[])  # 연결된 자녀 student_id 목록
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 관계
    user = relationship("User", foreign_keys=[user_id])

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
    plan_date = Column(Date, default=date.today)
    title = Column(String) # 해당 날짜 계획의 대표 명칭 (예: "기말고사 대비 수학 집중일")
    target_minutes = Column(Integer) # 그날 목표로 하는 순공 시간
    is_completed = Column(Boolean, default=False) 
    
    student = relationship("StudentProfile", back_populates="daily_plans")  
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
    completed_at = Column(DateTime, nullable=True)  # ← 추가!
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
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    student = relationship("StudentProfile", back_populates="analytics")  

# 10-1. 초기 진단 (학습 스타일 분석)
class DiagnosisLog(Base):
    __tablename__ = "diagnosis_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    
    # 과목별 분석
    subject = Column(String, nullable=False)  # "MATH", "KOREAN", "ENGLISH"
    
    # 풀이 습관 분석 결과
    solution_habit_summary = Column(Text)  # "논리적 전개는 훌륭하나 중간 연산..."
    detected_tags = Column(JSONB, default=[])  # ["논리적_전개", "계산_실수_주의"]
    
    # 메타데이터
    image_url = Column(String, nullable=True)  # 원본 이미지 저장 경로
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    student = relationship("StudentProfile", back_populates="diagnosis_logs")


# 10-2. 일반 학습 문제 분석
class ProblemAnalysisLog(Base):
    __tablename__ = "problem_analysis_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    
    # 문제 정보
    subject = Column(String, nullable=False)  # 과목 추가
    extracted_text = Column(Text)  # OCR로 추출된 문제 지문
    detected_concepts = Column(JSONB, default=[])  # ["로그함수", "방정식"]
    difficulty_level = Column(String)  # "상", "중", "하"
    
    # 오답 분석
    is_correct = Column(Boolean, default=False)  # 정답 여부 추가
    error_reason = Column(String, nullable=True)  # 틀렸을 때만
    ai_feedback_summary = Column(Text)  # 해당 문제 피드백
    
    # 메타데이터
    solved_at = Column(DateTime, default=datetime.now)
    
    # 관계
    student = relationship("StudentProfile", back_populates="problem_logs")
    chat_messages = relationship("ChatMessage", back_populates="problem_log")

# 11. 대화 맥락 저장
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
    
    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    student = relationship("StudentProfile", back_populates="chat_messages")
    problem_log = relationship("ProblemAnalysisLog", back_populates="chat_messages")


class StudentSentimentAnalysisLog(Base):
    """학생 상태 분석 로그 (상세 저장용)"""
    __tablename__ = "student_sentiment_analysis_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"))
    chat_message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id"))
    
    # 상세 분석 필드
    understanding_level = Column(String)  # 상/중/하
    emotional_state = Column(String)  # 긍정적/중립적/부정적/좌절감
    engagement_level = Column(String)  # 높음/보통/낮음
    confusion_points = Column(JSONB, default=[])
    question_type = Column(String)
    learning_signal = Column(String)
    needs_intervention = Column(Boolean)
    confidence_score = Column(Float)

    created_at = Column(DateTime, default=datetime.now)


# 일간 학습 리포트
class DailyReport(Base):
    """일간 학습 리포트 모델"""

    __tablename__ = "daily_reports"

    # Primary Key
    report_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="리포트 고유 ID"
    )

    # Foreign Key
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="유저 ID (users 테이블 참조)"
    )

    # 기본 정보
    report_date = Column(Date, nullable=False, index=True, comment="리포트 날짜")

    # 입력 데이터 (학습 통계)
    total_study_time = Column(Integer, nullable=False, comment="총 학습 시간(분)")
    achievement_rate = Column(Float, nullable=False, comment="평균 성취도(%)")
    question_count = Column(Integer, nullable=False, comment="총 질문 횟수")
    most_immersive_subject = Column(String(100), comment="가장 몰입한 과목")
    subject_details = Column(JSONB, comment="과목별 상세 정보")

    # AI 생성 컨텐츠
    ai_summary_title = Column(String(200), comment="AI 생성 요약 제목")
    ai_good_point = Column(Text, comment="AI 피드백: 잘한 점")
    ai_improvement_point = Column(Text, comment="AI 피드백: 개선 포인트")
    keywords = Column(JSONB, comment="키워드 배열 (3개)")
    passion_temp = Column(Float, comment="열정 온도 (36.5~100)")
    subject_badges = Column(JSONB, comment="과목별 배지")

    # 메타데이터
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 시각"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="수정 시각"
    )

    # 복합 인덱스 (사용자별 날짜 조회 최적화, 중복 방지)
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'report_date', unique=True),
    )

    def to_dict(self):
        """모델을 API 응답 형식으로 변환"""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "ai_summary_title": self.ai_summary_title,
            "ai_good_point": self.ai_good_point,
            "ai_improvement_point": self.ai_improvement_point,
            "keywords": self.keywords,
            "passion_temp": self.passion_temp,
            "subject_badges": self.subject_badges,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<DailyReport(user_id={self.user_id}, date={self.report_date}, temp={self.passion_temp}°C)>"