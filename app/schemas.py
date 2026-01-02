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



class AnalysisResultItem(BaseModel):
    analysis_id: UUID
    subject: str
    extracted_content: str
    detected_tags: List[str]

    model_config = ConfigDict(from_attributes=True)

# data: List[AnalysisResultItem] 구조가 됨
class AnalysisResponse(BaseResponse[List[AnalysisResultItem]]):
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


class RoutineCreateRequest(BaseModel):
    user_id: UUID = Field(..., description="유저 고유 ID")
    routines: List[RoutineBlockRequest] = Field(..., description="시간 블록 배열")

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

# --- [주간 가용 시간 조회 관련 스키마] ---

class DaySchedule(BaseModel):
    """요일별 학습 시간 스케줄"""
    day_of_week: str = Field(..., description="요일 (MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY)")
    recommended_minutes: int = Field(..., description="해당 요일 권장 학습 시간 (분)")
    source_type: str = Field(default="ROUTINE", description="시간 출처")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "day_of_week": "MONDAY",
                "recommended_minutes": 80,
                "source_type": "ROUTINE"
            }
        }
    )


class WeeklyScheduleData(BaseModel):
    """주간 스케줄 데이터"""
    weekly_schedule: List[DaySchedule] = Field(..., description="요일별 가용 시간 목록 (7개 요소)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "weekly_schedule": [
                    {
                        "day_of_week": "MONDAY",
                        "recommended_minutes": 80,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "TUESDAY", 
                        "recommended_minutes": 120,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "WEDNESDAY",
                        "recommended_minutes": 90,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "THURSDAY",
                        "recommended_minutes": 100,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "FRIDAY",
                        "recommended_minutes": 60,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "SATURDAY",
                        "recommended_minutes": 180,
                        "source_type": "ROUTINE"
                    },
                    {
                        "day_of_week": "SUNDAY",
                        "recommended_minutes": 150,
                        "source_type": "ROUTINE"
                    }
                ]
            }
        }
    )


class TimeSlotResponse(BaseResponse[WeeklyScheduleData]):
    """GET /students/{student_id}/time-slots 응답"""
    pass

# --- [주간 학습 계획 생성 관련 스키마] ---

class MissionCreateRequest(BaseModel):
    """주간 학습 계획 생성 요청"""
    start_date: Optional[str] = Field(
        None,
        description="계획 시작 날짜 (YYYY-MM-DD). 미입력 시 다음 월요일",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    @field_validator('start_date')
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용하세요. (입력값: {v})")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2026-01-06"
            }
        }
    )


class TaskDetail(BaseModel):
    """학습 과제 상세"""
    task_id: UUID = Field(..., description="과제 고유 ID")
    sequence: int = Field(..., description="순서 (1부터 시작)", ge=1)
    category: str = Field(..., description="과목명")
    title: str = Field(..., description="과제 제목")
    assigned_minutes: int = Field(..., description="할당 시간 (분)", gt=0)
    time_slot: str = Field(..., description="권장 시간대 (HH:MM-HH:MM)")
    difficulty_level: str = Field(..., description="난이도 (상/중/하)")
    problem_count: int = Field(..., description="예상 문제 수", ge=0)
    learning_objective: str = Field(..., description="학습 목표")
    instruction: str = Field(..., description="구체적인 학습 지침")
    rest_after: int = Field(..., description="과제 후 휴식 시간 (분)", ge=0)
    is_completed: bool = Field(default=False, description="완료 여부")

    model_config = ConfigDict(from_attributes=True)


class DailyPlanDetail(BaseModel):
    """일별 학습 계획"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    day_of_week: str = Field(..., description="요일 (MONDAY ~ SUNDAY)")
    total_available_minutes: int = Field(..., description="해당 날짜 총 가용 시간 (분)")
    total_planned_minutes: int = Field(..., description="해당 날짜 계획된 학습 시간 (분)")
    daily_focus: str = Field(..., description="당일 학습 초점")
    tasks: List[TaskDetail] = Field(..., description="학습 과제 목록")
    daily_summary: str = Field(..., description="당일 학습 요약")
    energy_distribution: str = Field(..., description="에너지 레벨 분포 (예: 상-상-중-하)")

    model_config = ConfigDict(from_attributes=True)


class WeeklySummaryDetail(BaseModel):
    """주간 요약"""
    expected_improvement: str = Field(..., description="예상 향상 효과")
    adaptive_notes: str = Field(..., description="학생 맞춤 특이사항")
    weekly_goals: List[str] = Field(..., description="주간 목표 리스트")

    model_config = ConfigDict(from_attributes=True)


class WeeklyPlanData(BaseModel):
    """주간 학습 계획 데이터"""
    plan_id: UUID = Field(..., description="생성된 주간 개별 계획 고유 ID")
    student_id: UUID = Field(..., description="학생 고유 ID")
    start_date: str = Field(..., description="계획 시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="계획 종료 날짜 (YYYY-MM-DD)")
    total_study_minutes: int = Field(..., description="주간 총 학습 시간 (분)")
    subject_distribution: dict = Field(..., description="과목별 시간 배분")
    focus_areas: List[str] = Field(..., description="주간 집중 영역")
    weekly_plan: List[DailyPlanDetail] = Field(..., description="일별 학습 계획 (7개 요소)")
    weekly_summary: WeeklySummaryDetail = Field(..., description="주간 요약 정보")
    created_at: str = Field(..., description="계획 생성 시각 (ISO 8601)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "plan_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "start_date": "2026-01-06",
                "end_date": "2026-01-12",
                "total_study_minutes": 780,
                "subject_distribution": {
                    "수학": 320,
                    "영어": 280,
                    "국어": 180
                },
                "focus_areas": [
                    "수학 계산 실수 교정",
                    "영어 세부 내용 파악",
                    "국어 문법 기초 다지기"
                ],
                "weekly_plan": [],
                "weekly_summary": {
                    "expected_improvement": "이번 주 계획을 완수하면 수학 계산 정확도 15% 향상",
                    "adaptive_notes": "SPEED_FIRST 유형에 맞춰 짧은 세션으로 구성",
                    "weekly_goals": ["수학: 이차방정식 완벽 마스터"]
                },
                "created_at": "2026-01-02T10:30:00Z"
            }
        }
    )


class MissionCreateResponse(BaseResponse[WeeklyPlanData]):
    """POST /my/missions 응답"""
    pass

# --- [대시보드 API 스키마] ---

class DashboardSummaryData(BaseModel):
    """대시보드 요약 정보"""
    student_name: str = Field(..., description="학생 이름")
    streak_days: int = Field(..., description="연속 학습 일수")
    today_available_minutes: int = Field(..., description="오늘 가용 시간 (분)")
    today_date: str = Field(..., description="오늘 날짜 (YYYY-MM-DD)")

    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseResponse[DashboardSummaryData]):
    """GET /my/dashboard 응답"""
    pass

class ScheduleTaskItem(BaseModel):
    """시간대(TimeSlot) 내부에 들어갈 상세 과제 정보"""
    task_id: UUID = Field(..., description="과제 고유 ID")
    category: str = Field(..., description="과목명 (예: 수학, 일정 없음)")
    title: str = Field(..., description="과제 제목")
    subtitle: str = Field(..., description="부제목 (예: 클릭하여 완료 표시)")
    assigned_minutes: int = Field(..., description="할당 시간 (분)")
    is_completed: bool = Field(..., description="완료 여부")
    status: str = Field(..., description="상태 (완료, 잠김, 진행 가능)")

    model_config = ConfigDict(from_attributes=True)

class TimeSlotSchedule(BaseModel):
    """명세서의 schedule 배열 요소 (시간 + 과제 객체)"""
    time_slot: str = Field(..., description="시간대 (HH:MM)")
    task: Optional[ScheduleTaskItem] = Field(None, description="해당 시간대의 과제 (없으면 null)")

    model_config = ConfigDict(from_attributes=True)

class TodayMissionData(BaseModel):
    """오늘의 미션 데이터 (최상위 구조)"""
    mission_date: str = Field(..., description="미션 날짜 (YYYY-MM-DD)")
    mission_title: Optional[str] = Field(None, description="미션 제목")
    total_minutes: int = Field(..., description="총 목표 시간 (분)")
    completion_rate: float = Field(..., description="완료율 (0-100)")
    # 프론트가 요구한 필드명 'schedule'
    schedule: List[TimeSlotSchedule] = Field(..., description="시간대별 스케줄 리스트")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "mission_date": "2026-01-02",
                "mission_title": "오늘의 학습 시간표",
                "total_minutes": 240,
                "completion_rate": 0,
                "schedule": [
                    {
                        "time_slot": "09:00",
                        "task": {
                            "task_id": "task-001-uuid",
                            "category": "응용 문제 연습",
                            "title": "응용 문제 연습",
                            "subtitle": "클릭하여 완료 표시",
                            "assigned_minutes": 60,
                            "is_completed": False,
                            "status": "진행 가능"
                        }
                    }
                ]
            }
        }
    )

class TodayMissionResponse(BaseResponse[TodayMissionData]):
    """GET /my/missions/today 응답 스키마"""
    pass


## 실시간 랭킹 조회
class RecentRankingItem(BaseModel):
    """실시간 랭킹 항목"""
    rank: int = Field(..., description="순위")
    user_id: str = Field(..., description="사용자 ID (익명화)")
    points: int = Field(..., description="포인트")
    points_change: str = Field(..., description="포인트 변화 (예: +90pts)")
    is_me: bool = Field(..., description="본인 여부")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "rank": 1,
                "user_id": "User_234",
                "points": 90,
                "points_change": "+90pts",
                "is_me": True
            }
        }
    )


class RecentRankingData(BaseModel):
    """실시간 랭킹 데이터"""
    my_rank: int = Field(..., description="내 순위 (같은 학년 내)")
    my_points: int = Field(..., description="내 포인트")
    recent_activities: List[RecentRankingItem] = Field(..., description="최근 활동 목록")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "my_rank": 1,
                "my_points": 90,
                "recent_activities": [
                    {
                        "rank": 1,
                        "user_id": "User_234",
                        "points": 90,
                        "points_change": "+90pts",
                        "is_me": True
                    },
                    {
                        "rank": 2,
                        "user_id": "B",
                        "points": 85,
                        "points_change": "+85pts",
                        "is_me": False
                    }
                ]
            }
        }
    )


class RecentRankingResponse(BaseResponse[RecentRankingData]):
    """GET /my/recent-ranking 응답"""
    pass

# 과목별 통계 요소
class SubjectStatItem(BaseModel):
    category: str = Field(..., description="과목명 (예: 수학, 영어 등)")
    total_count: int = Field(..., description="해당 월의 전체 과제 총 개수")
    completed_count: int = Field(..., description="해당 월에 완료된 과제 개수")
    achievement_rate: float = Field(..., description="해당 월의 누적 과제 완료율 (0.0 - 100.0)")

    model_config = ConfigDict(from_attributes=True)

# 응답 데이터 구조
class LearningStatsData(BaseModel):
    subject_stats: List[SubjectStatItem] = Field(..., description="월간 누적 과목별 학습 데이터 리스트")

# 최종 응답 스키마
class LearningStatsResponse(BaseResponse[LearningStatsData]):
    """GET /my/learning-stats 응답"""
    pass

