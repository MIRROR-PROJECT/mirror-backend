from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List
from uuid import UUID
import datetime
from datetime import date

from app.database import get_db
from app import models, schemas
from app.models import WeeklyRoutine, StudentProfile, User, DailyPlan, Task, DiagnosisLog
from app.dependencies import get_current_user
from app.services.weekly_plan_service import regenerate_daily_plan_for_date

router = APIRouter(
    prefix="/routines",
    tags=["routines"]
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_weekly_routines(
    request: schemas.RoutineCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """주간 루틴 등록"""
    
    # 1. user_id로 학생 프로필 찾기
    result = await db.execute(
        select(StudentProfile).filter(StudentProfile.user_id == request.user_id)
    )
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"유저 ID {request.user_id}에 해당하는 학생 프로필을 찾을 수 없습니다."
        )
    
    # 2. 새로운 루틴 생성
    created_routine_ids = []
    
    try:
        for routine_data in request.routines:
            # 시간 문자열을 time 객체로 변환
            start_time = datetime.datetime.strptime(
                routine_data.start_time, "%H:%M"
            ).time()
            end_time = datetime.datetime.strptime(
                routine_data.end_time, "%H:%M"
            ).time()
            
            # WeeklyRoutine 객체 생성
            new_routine = WeeklyRoutine(
                student_id=student.id,
                day_of_week=routine_data.day_of_week,
                start_time=start_time,
                end_time=end_time,
                total_minutes=routine_data.total_minutes
            )
            
            db.add(new_routine)
        
        await db.flush()

        for routine in db.new:
            if isinstance(routine, WeeklyRoutine):
                created_routine_ids.append(routine.id)
        
        await db.commit()
        
        return schemas.BaseResponse.success_res(
            data=created_routine_ids,
            message="주간 루틴 등록 성공",
            code=status.HTTP_201_CREATED
        )
        
    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"시간 형식 오류: {str(e)}"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"루틴 등록 중 오류 발생: {str(e)}"
        )


@router.patch("/", response_model=schemas.RoutineUpdateResponse, status_code=status.HTTP_200_OK)
async def update_student_routines(
    request: schemas.RoutineUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [시간표 관리] 주간 루틴 수정 및 AI 학습 계획 자동 재조정
    - 루틴 변경 시 영향받는 날짜의 학습 계획을 AI가 자동으로 재생성
    """
    
    print("\n" + "="*60)
    print("🔄 주간 루틴 수정 및 AI 계획 재생성")
    print("="*60)
    
    # 1. 학생 프로필 조회
    profile_result = await db.execute(
        select(StudentProfile).filter(
            StudentProfile.user_id == current_user_id
        )
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.RoutineUpdateResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다.",
            code=404
        )
    
    print(f"✅ 학생 프로필: {profile.id}")
    
    # 2. 유저 정보 조회
    user_result = await db.execute(
        select(User).filter(User.id == current_user_id)
    )
    user = user_result.scalars().first()
    
    # 3. 요청 검증
    if not request.routines:
        return schemas.RoutineUpdateResponse.fail_res(
            message="시간 블록이 비어있습니다.",
            code=400
        )
    
    # 4. 시간 중복 검증
    time_blocks_by_day = {}
    for routine in request.routines:
        day = routine.day_of_week
        if day not in time_blocks_by_day:
            time_blocks_by_day[day] = []
        time_blocks_by_day[day].append((routine.start_time, routine.end_time))
    
    for day, blocks in time_blocks_by_day.items():
        for i, (start1, end1) in enumerate(blocks):
            for j, (start2, end2) in enumerate(blocks):
                if i >= j:
                    continue
                # HH:MM 문자열 비교
                if not (end1 <= start2 or end2 <= start1):
                    return schemas.RoutineUpdateResponse.fail_res(
                        message=f"시간대 겹침: {day} {start1}-{end1}",
                        code=400
                    )
    
    print(f"✅ 시간 블록 검증 완료: {len(request.routines)}개")
    
    try:
        # 5. 기존 루틴 삭제
        delete_result = await db.execute(
            delete(WeeklyRoutine).filter(
                WeeklyRoutine.student_id == profile.id
            )
        )
        deleted_count = delete_result.rowcount
        print(f"🗑️  기존 루틴 삭제: {deleted_count}개")
        
        # 6. 새 루틴 생성
        new_routine_ids = []
        routines_by_day = {}  # 요일별 그룹핑
        
        for routine_data in request.routines:
            start_time = datetime.datetime.strptime(routine_data.start_time, "%H:%M").time()
            end_time = datetime.datetime.strptime(routine_data.end_time, "%H:%M").time()
            
            new_routine = WeeklyRoutine(
                student_id=profile.id,
                day_of_week=routine_data.day_of_week,
                start_time=start_time,
                end_time=end_time,
                total_minutes=routine_data.total_minutes,
                block_name=None,
                category=None
            )
            db.add(new_routine)
            await db.flush()
            
            new_routine_ids.append(new_routine.id)
            
            # 요일별 그룹핑
            if routine_data.day_of_week not in routines_by_day:
                routines_by_day[routine_data.day_of_week] = []
            routines_by_day[routine_data.day_of_week].append(new_routine)
            
            print(f"  ➕ {routine_data.day_of_week} {routine_data.start_time}-{routine_data.end_time}")
        
        print(f"✅ 새 루틴 생성: {len(new_routine_ids)}개")
        
        # 7. AI 계획 재생성 (무조건 실행)
        print("\n🤖 AI 학습 계획 재생성 시작...")
        
        # 7-1. 풀이 습관 조회
        diagnosis_logs_result = await db.execute(
            select(DiagnosisLog).filter(
                DiagnosisLog.student_id == profile.id
            )
        )
        diagnosis_logs = diagnosis_logs_result.scalars().all()
        
        if diagnosis_logs:
            solving_habits = "\n\n".join([
                f"### {log.subject}\n- 풀이 습관 요약: {log.solution_habit_summary}\n- 감지된 태그: {log.detected_tags}"
                for log in diagnosis_logs
            ])
        else:
            solving_habits = "### 풀이 습관 분석 데이터 없음\n이미지 기반 풀이 습관 분석이 제공되지 않았습니다."
        
        # 7-2. student_data 준비
        student_data = {
            'student_id': str(profile.id),
            'student_name': user.name if user else '학생',
            'school_grade': profile.school_grade,
            'semester': profile.semester,
            'subjects': profile.subjects,
            'cognitive_type': profile.cognitive_type.value
        }
        
        # 7-3. 오늘 이후 미완료 계획 조회
        today = date.today()
        
        future_plans_result = await db.execute(
            select(DailyPlan).filter(
                DailyPlan.student_id == profile.id,
                DailyPlan.plan_date >= today,
                DailyPlan.is_completed == False
            ).order_by(DailyPlan.plan_date)
        )
        future_plans = future_plans_result.scalars().all()
        
        print(f"📋 재생성 대상: {len(future_plans)}개 계획")
        
        # 7-4. 변경된 요일 식별
        changed_days = set(routines_by_day.keys())
        print(f"📅 변경된 요일: {', '.join(changed_days)}")
        
        # 7-5. 요일 매핑
        day_map_num_to_code = {
            0: "MON", 1: "TUE", 2: "WED", 3: "THU",
            4: "FRI", 5: "SAT", 6: "SUN"
        }
        
        regenerated_plans = []
        stats = {"regenerated": 0, "unchanged": 0, "failed": 0}
        
        # 7-6. 각 계획 처리
        for plan in future_plans:
            plan_day_code = day_map_num_to_code[plan.plan_date.weekday()]
            affected = plan_day_code in changed_days
            
            # 기존 Task 개수 및 시간 저장 (변경 전)
            old_tasks_result = await db.execute(
                select(Task).filter(Task.plan_id == plan.id)
            )
            old_tasks = old_tasks_result.scalars().all()
            old_tasks_count = len(old_tasks)
            old_minutes = sum(t.assigned_minutes for t in old_tasks)
            
            if affected:
                print(f"\n  🔄 {plan.plan_date} ({plan_day_code}) - AI 재생성 중...")
                
                # 해당 요일의 루틴 가져오기
                day_routines = routines_by_day.get(plan_day_code, [])
                
                if not day_routines:
                    print(f"    ⚠️  루틴 없음 - 건너뜀")
                    regenerated_plans.append(schemas.RegeneratedPlanItem(
                        plan_id=plan.id,
                        plan_date=plan.plan_date.strftime("%Y-%m-%d"),
                        day_of_week=plan_day_code,
                        affected=True,
                        status="failed",
                        tasks_count=old_tasks_count,
                        total_minutes=old_minutes,
                        changes=None,
                        error_message="해당 요일의 루틴이 없습니다"
                    ))
                    stats["failed"] += 1
                    continue
                
                # AI 계획 생성
                ai_plan = await regenerate_daily_plan_for_date(
                    db=db,
                    student_data=student_data,
                    target_date=plan.plan_date,
                    solving_habits=solving_habits,
                    day_routines=day_routines,
                    existing_plan_id=plan.id
                )
                
                if ai_plan:
                    # 기존 Task 삭제
                    await db.execute(
                        delete(Task).filter(Task.plan_id == plan.id)
                    )
                    
                    # DailyPlan 업데이트
                    plan.title = ai_plan.get('daily_focus', f"{plan.plan_date} 학습 계획")
                    plan.target_minutes = ai_plan.get('total_planned_minutes', 0)
                    
                    # 새 Task 생성
                    for task_data in ai_plan.get('tasks', []):
                        new_task = Task(
                            plan_id=plan.id,
                            category=task_data['category'],
                            title=task_data['title'],
                            assigned_minutes=task_data['assigned_minutes'],
                            is_completed=False,
                            sequence=task_data['sequence']
                        )
                        db.add(new_task)
                    
                    await db.flush()
                    
                    new_tasks_count = len(ai_plan.get('tasks', []))
                    new_minutes = ai_plan.get('total_planned_minutes', 0)
                    
                    print(f"    ✅ AI 재생성 완료: {new_tasks_count}개 Task")
                    
                    regenerated_plans.append(schemas.RegeneratedPlanItem(
                        plan_id=plan.id,
                        plan_date=plan.plan_date.strftime("%Y-%m-%d"),
                        day_of_week=plan_day_code,
                        affected=True,
                        status="regenerated",
                        tasks_count=new_tasks_count,
                        total_minutes=new_minutes,
                        changes=schemas.PlanChanges(
                            old_tasks_count=old_tasks_count,
                            new_tasks_count=new_tasks_count,
                            old_minutes=old_minutes,
                            new_minutes=new_minutes
                        ),
                        error_message=None
                    ))
                    stats["regenerated"] += 1
                else:
                    print(f"    ❌ AI 재생성 실패")
                    
                    regenerated_plans.append(schemas.RegeneratedPlanItem(
                        plan_id=plan.id,
                        plan_date=plan.plan_date.strftime("%Y-%m-%d"),
                        day_of_week=plan_day_code,
                        affected=True,
                        status="failed",
                        tasks_count=old_tasks_count,
                        total_minutes=old_minutes,
                        changes=None,
                        error_message="AI 계획 생성 실패"
                    ))
                    stats["failed"] += 1
            else:
                print(f"  ⏭️  {plan.plan_date} ({plan_day_code}) - 유지")
                
                regenerated_plans.append(schemas.RegeneratedPlanItem(
                    plan_id=plan.id,
                    plan_date=plan.plan_date.strftime("%Y-%m-%d"),
                    day_of_week=plan_day_code,
                    affected=False,
                    status="unchanged",
                    tasks_count=old_tasks_count,
                    total_minutes=old_minutes,
                    changes=None,
                    error_message=None
                ))
                stats["unchanged"] += 1
        
        print(f"\n✅ AI 재생성 완료:")
        print(f"  - 재생성: {stats['regenerated']}개")
        print(f"  - 유지: {stats['unchanged']}개")
        print(f"  - 실패: {stats['failed']}개")
        
        # 8. 커밋
        await db.commit()
        print("✅ DB 커밋 완료")
        print("="*60 + "\n")
        
        # 9. 응답
        response_data = schemas.RoutineUpdateData(
            updated_routine_ids=new_routine_ids,
            deleted_count=deleted_count,
            regenerated_plans=regenerated_plans,
            summary=schemas.RegenerationSummary(
                total_plans=len(regenerated_plans),
                regenerated=stats["regenerated"],
                unchanged=stats["unchanged"],
                failed=stats["failed"]
            )
        )
        
        return schemas.RoutineUpdateResponse.success_res(
            data=response_data,
            message="주간 루틴 수정 및 AI 학습 계획 재조정 완료",
            code=200
        )
        
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        return schemas.RoutineUpdateResponse.fail_res(
            message=f"루틴 수정 중 오류: {str(e)}",
            code=500
        )