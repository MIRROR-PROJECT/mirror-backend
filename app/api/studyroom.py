from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timedelta

from ..database import get_db
from ..models import StudentProfile, DailyPlan, Task
from ..schemas import (
    SimpleWeeklyPlanResponse,
    SimpleWeeklyPlanData,
    SimpleWeeklyDailyPlan,
    SimpleWeeklyTaskItem
)
from ..dependencies import get_current_user

router = APIRouter(
    prefix="/studyroom",
    tags=["studyroom"]
)


def get_week_start(date_str: Optional[str] = None) -> datetime:
    """
    주의 시작일(월요일) 계산
    """
    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        target_date = datetime.now()
    
    # 월요일까지 며칠 남았는지 계산
    days_to_monday = target_date.weekday()
    monday = target_date - timedelta(days=days_to_monday)
    
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get(
    "/weekly-plan",
    response_model=SimpleWeeklyPlanResponse,
    summary="일주일치 학습 계획 조회",
    description="특정 주의 학습 계획을 조회합니다. start_date를 기준으로 해당 주의 7일치 계획을 반환합니다."
)
async def get_weekly_plan(
    start_date: Optional[str] = Query(
        None,
        description="조회할 주의 시작 날짜 (YYYY-MM-DD, 월요일)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    ),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일주일치 학습 계획 조회
    """
    
    try:
        # 1. 날짜 검증 및 계산
        if start_date:
            try:
                target_monday = datetime.strptime(start_date, "%Y-%m-%d")
                # 월요일인지 확인
                if target_monday.weekday() != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="start_date는 월요일이어야 합니다"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용해주세요"
                )
        else:
            target_monday = get_week_start()
        
        # 주의 시작일과 종료일
        week_start = target_monday.date()
        week_end = week_start + timedelta(days=6)
        
        # 2. 학생 프로필 조회
        profile_result = await db.execute(
            select(StudentProfile).filter(StudentProfile.user_id == current_user_id)
        )
        profile = profile_result.scalars().first()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="학생 프로필을 찾을 수 없습니다"
            )
        
        # 3. 해당 주의 DailyPlan 조회 (Task 포함)
        daily_plans_result = await db.execute(
            select(DailyPlan)
            .options(selectinload(DailyPlan.tasks))
            .filter(
                and_(
                    DailyPlan.student_id == profile.id,
                    DailyPlan.plan_date >= week_start,
                    DailyPlan.plan_date <= week_end
                )
            )
            .order_by(DailyPlan.plan_date)
        )
        daily_plans = daily_plans_result.scalars().all()
        
        if not daily_plans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 기간의 학습 계획이 없습니다"
            )
        
        # 4. 요일 매핑
        day_map = {
            0: "MONDAY",
            1: "TUESDAY",
            2: "WEDNESDAY",
            3: "THURSDAY",
            4: "FRIDAY",
            5: "SATURDAY",
            6: "SUNDAY"
        }
        
        # 5. weekly_plan 생성
        weekly_plan_list = []
        
        for daily_plan in daily_plans:
            # Task 정렬 (sequence 순)
            sorted_tasks = sorted(daily_plan.tasks, key=lambda t: t.sequence)
            
            # 일일 통계 계산
            daily_planned = sum(task.assigned_minutes for task in sorted_tasks)
            daily_completed = sum(
                task.assigned_minutes for task in sorted_tasks if task.is_completed
            )
            daily_completion_rate = (
                (daily_completed / daily_planned * 100) if daily_planned > 0 else 0.0
            )
            
            # Task 리스트 생성
            task_items = [
                SimpleWeeklyTaskItem(
                    task_id=task.id,
                    sequence=task.sequence,
                    category=task.category,
                    title=task.title,
                    assigned_minutes=task.assigned_minutes,
                    is_completed=task.is_completed,
                    completed_at=(
                        task.completed_at.isoformat() + "Z" 
                        if task.completed_at else None
                    )
                )
                for task in sorted_tasks
            ]
            
            # 요일 계산
            day_of_week = day_map[daily_plan.plan_date.weekday()]
            
            # DailyPlan 추가
            weekly_plan_list.append(
                SimpleWeeklyDailyPlan(
                    plan_id=daily_plan.id,
                    date=daily_plan.plan_date.strftime("%Y-%m-%d"),
                    day_of_week=day_of_week,
                    title=daily_plan.title,
                    total_planned_minutes=daily_planned,
                    total_completed_minutes=daily_completed,
                    completion_rate=round(daily_completion_rate, 2),
                    is_completed=daily_plan.is_completed,
                    tasks=task_items
                )
            )
        
        # 6. 응답 데이터 생성
        response_data = SimpleWeeklyPlanData(
            student_id=profile.id,
            start_date=week_start.strftime("%Y-%m-%d"),
            end_date=week_end.strftime("%Y-%m-%d"),
            weekly_plan=weekly_plan_list
        )
        
        return SimpleWeeklyPlanResponse.success_res(
            data=response_data,
            message="주간 학습 계획 조회 성공"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )
