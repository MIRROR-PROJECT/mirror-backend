from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, UUID4
from uuid import UUID
from datetime import date, time, datetime
from typing import List, Optional, Generic, TypeVar, Any
from .models import CognitiveType
import uuid
from enum import Enum
import re

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


# --- [온보딩 역할 선택 관련 스키마] ---

class RoleType(str, Enum):
    """사용자 역할 타입"""
    STUDENT = "student"
    TEACHER = "teacher"
    PARENT = "parent"


class RoleSelectionRequest(BaseModel):
    """역할 선택 요청"""
    role: RoleType = Field(
        ..., 
        description="사용자 역할 (student, teacher, parent)",
        example="student"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "student"
            }
        }
    )

class RoleSelectionData(BaseModel):
    """역할 선택 응답 데이터"""
    user_id: UUID = Field(..., description="사용자 고유 식별자")
    role: str = Field(..., description="저장된 역할")
    role_id: UUID = Field(..., description="역할별 테이블의 고유 ID (student_id/teacher_id/parent_id)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
                "role": "student",
                "role_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33"
            }
        }
    )

class RoleSelectionResponse(BaseResponse[RoleSelectionData]):
    """POST /onboarding/role 응답"""
    pass


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
    problem_count: int = Field(default=0, description="예상 문제 수", ge=0)
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

# --- [태스크 완료 여부 변경 관련 스키마] ---

class TaskToggleData(BaseModel):
    """태스크 상태 변경 응답 데이터"""
    task_id: UUID
    is_completed: bool

class TaskToggleResponse(BaseResponse[TaskToggleData]):
    """PATCH /my/tasks/{task_id}/toggle 응답"""
    pass



# --- Request 스키마 ---

class RoutineUpdateRequest(BaseModel):
    """주간 루틴 수정 요청 (항상 AI 재생성)"""
    user_id: UUID = Field(..., description="학생 고유 ID")
    routines: List[RoutineBlockRequest] = Field(..., description="새로운 시간 블록 배열")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "a3b5c7d9-1234-5678-90ab-cdef12345678",
                "routines": [
                    {
                        "day_of_week": "MON",
                        "start_time": "10:00",
                        "end_time": "12:00",
                        "total_minutes": 120
                    }
                ]
            }
        }
    )


# --- Response 스키마 ---

class PlanChanges(BaseModel):
    """계획 변경 정보"""
    old_tasks_count: int = Field(..., description="변경 전 Task 개수")
    new_tasks_count: int = Field(..., description="변경 후 Task 개수")
    old_minutes: int = Field(..., description="변경 전 총 학습 시간")
    new_minutes: int = Field(..., description="변경 후 총 학습 시간")


class RegeneratedPlanItem(BaseModel):
    """재생성된 계획 항목"""
    plan_id: UUID = Field(..., description="DailyPlan ID")
    plan_date: str = Field(..., description="계획 날짜 (YYYY-MM-DD)")
    day_of_week: str = Field(..., description="요일 (MON, TUE, ...)")
    affected: bool = Field(..., description="루틴 변경으로 영향받았는지")
    status: str = Field(..., description="regenerated, unchanged, failed")
    tasks_count: int = Field(..., description="Task 개수")
    total_minutes: int = Field(..., description="총 학습 시간 (분)")
    changes: Optional[PlanChanges] = Field(None, description="변경 전후 비교")
    error_message: Optional[str] = Field(None, description="실패 시 오류 메시지")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "plan_date": "2026-01-06",
                "day_of_week": "MON",
                "affected": True,
                "status": "regenerated",
                "tasks_count": 4,
                "total_minutes": 110,
                "changes": {
                    "old_tasks_count": 3,
                    "new_tasks_count": 4,
                    "old_minutes": 90,
                    "new_minutes": 110
                },
                "error_message": None
            }
        }
    )


class RegenerationSummary(BaseModel):
    """재생성 통계"""
    total_plans: int = Field(..., description="전체 처리된 계획 개수")
    regenerated: int = Field(..., description="재생성된 계획 개수")
    unchanged: int = Field(..., description="유지된 계획 개수")
    failed: int = Field(..., description="실패한 계획 개수")


class RoutineUpdateData(BaseModel):
    """주간 루틴 수정 응답 데이터"""
    updated_routine_ids: List[UUID] = Field(..., description="수정된 루틴 ID 목록")
    deleted_count: int = Field(..., description="삭제된 기존 루틴 개수")
    regenerated_plans: List[RegeneratedPlanItem] = Field(..., description="재생성된 학습 계획 목록")
    summary: RegenerationSummary = Field(..., description="재생성 통계")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "updated_routine_ids": [
                    "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "8d3e4f5a-6b7c-8d9e-0f1a-2b3c4d5e6f7a"
                ],
                "deleted_count": 5,
                "regenerated_plans": [
                    {
                        "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "plan_date": "2026-01-06",
                        "day_of_week": "MON",
                        "affected": True,
                        "status": "regenerated",
                        "tasks_count": 4,
                        "total_minutes": 110,
                        "changes": {
                            "old_tasks_count": 3,
                            "new_tasks_count": 4,
                            "old_minutes": 90,
                            "new_minutes": 110
                        }
                    }
                ],
                "summary": {
                    "total_plans": 7,
                    "regenerated": 3,
                    "unchanged": 4,
                    "failed": 0
                }
            }
        }
    )


class RoutineUpdateResponse(BaseResponse[RoutineUpdateData]):
    """PATCH /students/routines 응답"""
    pass



# --- [일주일치 학습 계획 조회 관련 스키마] ---

class SimpleWeeklyTaskItem(BaseModel):
    """주간 조회용 Task 항목"""
    task_id: UUID = Field(..., description="과제 고유 ID")
    sequence: int = Field(..., description="순서")
    category: str = Field(..., description="과목명")
    title: str = Field(..., description="과제 제목")
    assigned_minutes: int = Field(..., description="할당 시간 (분)")
    is_completed: bool = Field(..., description="완료 여부")
    completed_at: Optional[str] = Field(None, description="완료 시각 (ISO 8601)")

    model_config = ConfigDict(from_attributes=True)


class SimpleWeeklyDailyPlan(BaseModel):
    """주간 조회용 일일 계획"""
    plan_id: UUID = Field(..., description="일일 계획 ID")
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    day_of_week: str = Field(..., description="요일")
    title: str = Field(..., description="계획 제목")
    total_planned_minutes: int = Field(..., description="계획된 총 시간 (분)")
    total_completed_minutes: int = Field(..., description="완료된 시간 (분)")
    completion_rate: float = Field(..., description="완료율 (0-100)")
    is_completed: bool = Field(..., description="전체 완료 여부")
    tasks: List[SimpleWeeklyTaskItem] = Field(..., description="과제 목록")

    model_config = ConfigDict(from_attributes=True)


class SimpleWeeklyPlanData(BaseModel):
    """주간 계획 조회 응답 데이터"""
    student_id: UUID = Field(..., description="학생 ID")
    start_date: str = Field(..., description="시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료 날짜 (YYYY-MM-DD)")
    weekly_plan: List[SimpleWeeklyDailyPlan] = Field(..., description="일별 계획 (7개)")

    model_config = ConfigDict(from_attributes=True)


class SimpleWeeklyPlanResponse(BaseResponse[SimpleWeeklyPlanData]):
    """GET /studyroom/weekly-plan 응답"""
    pass

# --- [AI 튜터 채팅 관련 스키마] ---

class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., description="사용자 메시지", min_length=1)
    problem_log_id: Optional[UUID] = Field(None, description="특정 문제 관련 대화인 경우")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "이차방정식 풀이 방법을 알려주세요",
                "problem_log_id": None
            }
        }
    )


class StudentSentimentAnalysis(BaseModel):
    """학생 상태 분석 상세"""
    understanding_level: str = Field(..., description="이해도 수준 (상/중/하)")
    emotional_state: str = Field(..., description="감정 상태 (긍정적/중립적/부정적/좌절감)")
    engagement_level: str = Field(..., description="참여도 (높음/보통/낮음)")
    confusion_points: List[str] = Field(default=[], description="혼란스러워하는 개념")
    question_type: str = Field(..., description="질문 유형 (개념질문/풀이질문/확인질문/심화질문)")
    learning_signal: str = Field(..., description="학습 신호 (이해함/이해중/혼란/어려움/관심)")
    needs_intervention: bool = Field(..., description="교사 개입 필요 여부")
    confidence_score: float = Field(..., description="학생 자신감 점수 (0-100)", ge=0, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "understanding_level": "중",
                "emotional_state": "긍정적",
                "engagement_level": "높음",
                "confusion_points": ["근의 공식 유도 과정"],
                "question_type": "개념질문",
                "learning_signal": "이해중",
                "needs_intervention": False,
                "confidence_score": 65.0
            }
        }
    )


class ChatResponseData(BaseModel):
    """채팅 응답 데이터"""
    user_message_id: UUID = Field(..., description="사용자 메시지 ID")
    assistant_message_id: UUID = Field(..., description="AI 응답 메시지 ID")
    user_message: str = Field(..., description="사용자 메시지")
    assistant_message: str = Field(..., description="AI 응답")
    student_sentiment: StudentSentimentAnalysis = Field(..., description="학생 상태 상세 분석")
    created_at: str = Field(..., description="생성 시각 (ISO 8601)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_message_id": "msg-user-001-uuid",
                "assistant_message_id": "msg-ai-002-uuid",
                "user_message": "이차방정식 풀이 방법을 알려주세요",
                "assistant_message": "이차방정식을 푸는 방법은...",
                "student_sentiment": {
                    "understanding_level": "중",
                    "emotional_state": "긍정적",
                    "engagement_level": "높음",
                    "confusion_points": [],
                    "question_type": "개념질문",
                    "learning_signal": "이해중",
                    "needs_intervention": False,
                    "confidence_score": 70.0
                },
                "created_at": "2026-01-03T10:30:00Z"
            }
        }
    )


class ChatResponse(BaseResponse[ChatResponseData]):
    """POST /chat 응답"""
    pass


# --- [채팅 히스토리 조회 관련 스키마] ---

class ChatHistoryItem(BaseModel):
    """채팅 메시지 항목"""
    message_id: UUID = Field(..., description="메시지 ID")
    role: str = Field(..., description="역할 (user/assistant)")
    content: str = Field(..., description="메시지 내용")
    student_sentiment: Optional[str] = Field(None, description="학생 상태")
    created_at: str = Field(..., description="생성 시각 (ISO 8601)")
    problem_log_id: Optional[UUID] = Field(None, description="연결된 문제 ID")

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryData(BaseModel):
    """채팅 히스토리 데이터"""
    total_count: int = Field(..., description="총 메시지 수")
    messages: List[ChatHistoryItem] = Field(..., description="메시지 목록")

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseResponse[ChatHistoryData]):
    """GET /chat/history 응답"""
    pass


# --- [선생님 대시보드 - 학생 진도율 조회 스키마] ---

class WeaknessAnalysis(BaseModel):
    """학생 취약점 분석"""
    weak_concepts: List[str] = Field(default=[], description="취약한 개념 목록")
    error_patterns: List[str] = Field(default=[], description="주요 오답 패턴")
    struggling_subjects: List[str] = Field(default=[], description="어려움을 겪는 과목")
    recent_struggles: int = Field(default=0, description="최근 어려움 호소 횟수 (7일)", ge=0)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "weak_concepts": ["로그 법칙", "이차방정식"],
                "error_patterns": ["계산 실수", "개념 혼동"],
                "struggling_subjects": ["수학"],
                "recent_struggles": 5
            }
        }
    )


class StudentProgressSimple(BaseModel):
    """학생 진도율 정보 (간소화)"""
    student_id: UUID = Field(..., description="학생 프로필 ID")
    student_name: str = Field(..., description="학생 이름")
    phone_number: Optional[str] = Field(None, description="전화번호")
    profile_initial: str = Field(..., description="프로필 이니셜 (1글자)")
    class_label: str = Field(..., description="소속 반 이름")
    progress_rate: float = Field(..., description="학습 진도율 (0-100)", ge=0, le=100)
    progress_trend: str = Field(..., description="진도율 추세 (up/down/stable)")
    weakness_analysis: WeaknessAnalysis = Field(..., description="취약점 분석")
    last_active_at: Optional[str] = Field(None, description="마지막 활동 시각 (ISO 8601)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "student_id": "student-001-uuid",
                "student_name": "박민수",
                "phone_number": "010-1234-5678",
                "profile_initial": "박",
                "class_label": "고2 수리논술 심화반 A",
                "progress_rate": 42.0,
                "progress_trend": "down",
                "weakness_analysis": {
                    "weak_concepts": ["로그 법칙", "이차방정식"],
                    "error_patterns": ["계산 실수", "개념 혼동"],
                    "struggling_subjects": ["수학"],
                    "recent_struggles": 5
                },
                "last_active_at": "2026-01-03T15:30:00Z"
            }
        }
    )


class ClassInfoBasic(BaseModel):
    """반 정보 (기본)"""
    class_id: UUID = Field(..., description="반 ID")
    class_name: str = Field(..., description="반 이름")
    academy_name: Optional[str] = Field(None, description="학원 이름")

    model_config = ConfigDict(from_attributes=True)


class StudentProgressDataSimple(BaseModel):
    """학생 진도율 조회 응답 데이터 (간소화)"""
    class_info: ClassInfoBasic = Field(..., description="반 정보")
    period_start: str = Field(..., description="조회 시작 날짜 (YYYY-MM-DD)")
    period_end: str = Field(..., description="조회 종료 날짜 (YYYY-MM-DD)")
    total_students: int = Field(..., description="전체 학생 수")
    students: List[StudentProgressSimple] = Field(..., description="학생 목록")

    model_config = ConfigDict(from_attributes=True)


class StudentProgressResponseSimple(BaseResponse[StudentProgressDataSimple]):
    """GET /teacher/classes/{class_id}/students/progress 응답"""
    pass


# --- [선생님 - 반 목록 조회 스키마] ---

class TeacherClassItem(BaseModel):
    """선생님 반 정보"""
    class_id: UUID = Field(..., description="반 ID (StudentClassMatch의 대표 id)")
    class_name: str = Field(..., description="반 이름")
    academy_name: Optional[str] = Field(None, description="학원 이름")
    student_count: int = Field(..., description="해당 반 학생 수", ge=0)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "class_id": "class-001-uuid",
                "class_name": "고2 수학 A반",
                "academy_name": "서울학원",
                "student_count": 20
            }
        }
    )


class TeacherClassListData(BaseModel):
    """선생님 반 목록 데이터"""
    total_classes: int = Field(..., description="전체 반 수", ge=0)
    classes: List[TeacherClassItem] = Field(..., description="반 목록")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_classes": 3,
                "classes": [
                    {
                        "class_id": "class-001-uuid",
                        "class_name": "고1 수학 기초반",
                        "academy_name": "서울학원",
                        "student_count": 15
                    },
                    {
                        "class_id": "class-002-uuid",
                        "class_name": "고2 수학 A반",
                        "academy_name": "서울학원",
                        "student_count": 20
                    }
                ]
            }
        }
    )


class TeacherClassListResponse(BaseResponse[TeacherClassListData]):
    """GET /teacher/my-classes 응답"""
    pass



# --- [선생님 - 학생 추가 스키마] ---

import re
from pydantic import field_validator

class AddStudentRequest(BaseModel):
    """학생 추가 요청"""
    student_name: str = Field(..., description="학생 이름", min_length=2, max_length=50)
    phone_number: str = Field(..., description="전화번호 (010-XXXX-XXXX)")
    class_name: str = Field(..., description="반 이름 (선생님의 기존 반 중 선택)")
    email: Optional[str] = Field(None, description="이메일 (없으면 자동 생성)")
    school_grade: Optional[int] = Field(None, description="학년 (1-12)", ge=1, le=12)

    @field_validator('phone_number')
    def validate_phone(cls, v):
        """전화번호 형식 검증"""
        pattern = r'^010-\d{4}-\d{4}$'
        if not re.match(pattern, v):
            raise ValueError('전화번호 형식이 올바르지 않습니다 (010-XXXX-XXXX)')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_name": "박민수",
                "phone_number": "010-1234-5678",
                "class_name": "고2 수학 A반",
                "email": "student001@example.com",
                "school_grade": 11
            }
        }
    )


class AddStudentResponseData(BaseModel):
    """학생 추가 응답 데이터"""
    student_id: UUID = Field(..., description="생성된 학생 프로필 ID")
    user_id: UUID = Field(..., description="생성된 유저 ID")
    student_name: str = Field(..., description="학생 이름")
    phone_number: str = Field(..., description="전화번호")
    email: str = Field(..., description="이메일")
    class_name: str = Field(..., description="배정된 반 이름")
    academy_name: Optional[str] = Field(None, description="학원 이름")
    created_at: str = Field(..., description="생성 시각 (ISO 8601)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "student_id": "student-001-uuid",
                "user_id": "user-001-uuid",
                "student_name": "박민수",
                "phone_number": "010-1234-5678",
                "email": "student001@example.com",
                "class_name": "고2 수학 A반",
                "academy_name": "서울학원",
                "created_at": "2026-01-04T12:00:00Z"
            }
        }
    )


class AddStudentResponse(BaseResponse[AddStudentResponseData]):
    """POST /teacher/students 응답"""
    pass


# --- [선생님 - 상세 정보 등록 스키마] ---

class TeacherProfileRequest(BaseModel):
    """선생님 상세 정보 등록 요청"""
    phone_number: str = Field(..., description="선생님 연락처 (예: 010-1234-5678)")
    academy_name: str = Field(..., description="소속 학원명")

    @field_validator('phone_number')
    def validate_phone(cls, v):
        """전화번호 형식 검증"""
        pattern = r'^010-\d{4}-\d{4}$'
        if not re.match(pattern, v):
            raise ValueError('전화번호 형식이 올바르지 않습니다 (010-XXXX-XXXX)')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone_number": "010-1234-5678",
                "academy_name": "일등 수학학원"
            }
        }
    )

class TeacherProfileResponseData(BaseModel):
    """선생님 상세 정보 등록 응답 데이터"""
    teacher_id: UUID = Field(..., description="선생님 프로필 ID")
    academy_name: str = Field(..., description="소속 학원명")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "teacher_id": "d1ffcc88-8d1c-5fg9-cc7e-7cc0ce491b44",
                "academy_name": "일등 수학학원"
            }
        }
    )

class TeacherProfileResponse(BaseResponse[TeacherProfileResponseData]):
    """POST /teacher/profile 응답"""
    pass


# --- [학부모 - 상세 정보 등록 스키마] ---

class ParentProfileRequest(BaseModel):
    """학부모 상세 정보 등록 요청"""
    child_name: str = Field(..., description="자녀의 이름")
    child_phone: str = Field(..., description="자녀 연락처")
    parent_phone: str = Field(..., description="학부모 연락처")

    @field_validator('parent_phone', 'child_phone')
    def validate_phone(cls, v):
        """전화번호 형식 검증"""
        pattern = r'^010-\d{4}-\d{4}$'
        if not re.match(pattern, v):
            raise ValueError('전화번호 형식이 올바르지 않습니다 (010-XXXX-XXXX)')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "child_name": "김철수",
                "child_phone": "010-1111-2222",
                "parent_phone": "010-9876-5432"
            }
        }
    )

class ParentProfileResponseData(BaseModel):
    """학부모 상세 정보 등록 응답 데이터"""
    parent_id: UUID = Field(..., description="학부모 프로필 ID")
    child_name: str = Field(..., description="자녀의 이름")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "parent_id": "e2ggdd99-9e2d-6hh0-dd8f-8dd1df502c55",
                "child_name": "김철수"
            }
        }
    )

class ParentProfileResponse(BaseResponse[ParentProfileResponseData]):
    """POST /parents/profile 응답"""
    pass




# ============================================================================
# Request 스키마
# ============================================================================

class SubjectDetailRequest(BaseModel):
    """과목별 상세 정보"""
    subject_name: str = Field(..., description="과목명")
    mission_achievement_rate: float = Field(..., ge=0, le=100, description="미션 달성률 (%)")
    question_count: int = Field(..., ge=0, description="질문 횟수")


class DailyReportCreateRequest(BaseModel):
    """일간 리포트 생성 요청"""
    user_id: UUID4 = Field(..., description="유저 고유 식별자 (users 테이블의 ID)")
    report_date: Optional[str] = Field(None, description="리포트 날짜 (YYYY-MM-DD)")
    total_study_time: int = Field(..., ge=0, description="총 학습 시간 (분)")
    achievement_rate: float = Field(..., ge=0, le=100, description="평균 성취도 (%)")
    question_count: int = Field(..., ge=0, description="총 질문 횟수")
    most_immersive_subject: str = Field(..., description="가장 몰입한 과목")
    subject_details: List[SubjectDetailRequest] = Field(..., min_length=1, description="과목별 상세 정보")

    @field_validator('report_date')
    @classmethod
    def validate_date(cls, v):
        """날짜 형식 검증"""
        if v is None:
            return date.today().isoformat()
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("날짜 형식은 YYYY-MM-DD 여야 합니다")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
                "report_date": "2026-01-04",
                "total_study_time": 128,
                "achievement_rate": 77.0,
                "question_count": 2,
                "most_immersive_subject": "영어",
                "subject_details": [
                    {
                        "subject_name": "물리",
                        "mission_achievement_rate": 100.0,
                        "question_count": 0
                    },
                    {
                        "subject_name": "수학",
                        "mission_achievement_rate": 50.0,
                        "question_count": 0
                    },
                    {
                        "subject_name": "영어",
                        "mission_achievement_rate": 0.0,
                        "question_count": 2
                    }
                ]
            }
        }


# ============================================================================
# Response 데이터 스키마
# ============================================================================

class DailyReportData(BaseModel):
    """리포트 데이터"""
    report_id: UUID4 = Field(..., description="시스템에서 생성된 리포트 고유 ID")
    user_id: UUID4 = Field(..., description="리포트와 연결된 유저 ID")
    report_date: str = Field(..., description="리포트 날짜")
    ai_summary_title: str = Field(..., description="AI가 생성한 한 줄 요약 제목")
    ai_good_point: str = Field(..., description="AI 피드백: 잘한 점")
    ai_improvement_point: str = Field(..., description="AI 피드백: 개선 포인트")
    keywords: List[str] = Field(..., description="오늘의 키워드 3개")
    passion_temp: float = Field(..., description="열정 온도 (36.5 ~ 100.0)")
    subject_badges: List[str] = Field(..., description="과목별 상태 배지")
    created_at: str = Field(..., description="리포트 생성 시각 (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
                "user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
                "report_date": "2026-01-04",
                "ai_summary_title": "✨ 균형 잡힌 학습 습관",
                "ai_good_point": "2시간 8분 동안 성실하게 과제를 수행했습니다.",
                "ai_improvement_point": "내일은 평소에 어려워했던 과목에 30분만 더 투자해보세요.",
                "keywords": ["#균형", "#꾸준함", "#성장"],
                "passion_temp": 52.5,
                "subject_badges": ["🏃‍♂️ 진도 쑥쑥", "✨ 성실함", "🤔 개념 탐구"],
                "created_at": "2026-01-04T10:30:00Z"
            }
        }


class ReportHistoryData(BaseModel):
    """리포트 히스토리 데이터"""
    reports: List[DailyReportData]
    total_count: int
    date_range: dict
    statistics: dict


# ============================================================================
# Mirror 프로젝트 표준 응답 형식
# ============================================================================

class APIResponse(BaseModel):
    """표준 API 응답"""
    success: bool = Field(..., description="요청 처리 성공 여부")
    code: int = Field(..., description="HTTP 상태 코드")
    message: str = Field(..., description="처리 결과 메시지")
    data: Optional[DailyReportData] = Field(None, description="응답 데이터")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "code": 201,
                "message": "일간 리포트 생성 완료",
                "data": {
                    "report_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
                    "user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
                    "report_date": "2026-01-04",
                    "ai_summary_title": "✨ 균형 잡힌 학습 습관",
                    "ai_good_point": "2시간 8분 동안 성실하게 과제를 수행했습니다.",
                    "ai_improvement_point": "내일은 평소에 어려워했던 과목에 30분만 더 투자해보세요.",
                    "keywords": ["#균형", "#꾸준함", "#성장"],
                    "passion_temp": 52.5,
                    "subject_badges": ["🏃‍♂️ 진도 쑥쑥", "✨ 성실함", "🤔 개념 탐구"],
                    "created_at": "2026-01-04T10:30:00Z"
                }
            }
        }


class HistoryAPIResponse(BaseModel):
    """히스토리 API 응답"""
    success: bool
    code: int
    message: str
    data: Optional[ReportHistoryData] = None


class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = False
    code: int = Field(..., description="HTTP 에러 코드")
    message: str = Field(..., description="에러 메시지")
    data: None = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "code": 400,
                "message": "입력 데이터 유효성 검증 실패: achievement_rate는 0-100 사이의 값이어야 합니다",
                "data": None
            }
        }
