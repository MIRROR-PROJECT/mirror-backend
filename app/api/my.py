from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, func
from typing import List, Optional
import uuid
from datetime import datetime, timedelta, date

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.weekly_plan_service import generate_weekly_plan, calculate_weekly_summary

router = APIRouter(prefix="/my", tags=["My"])


@router.get("/time-slots", response_model=schemas.TimeSlotResponse)
async def get_student_time_slots(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    학생의 주간 가용 시간 가이드 조회
    - WeeklyRoutine 테이블에서 요일별 루틴을 조회하여 권장 학습 시간을 계산합니다.
    """
    profile_result = await db.execute(
        select(models.StudentProfile).filter(models.StudentProfile.user_id == current_user_id)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.TimeSlotResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다. 먼저 프로필을 생성해주세요.",
            code=404
        )
    
    routines_result = await db.execute(
        select(models.WeeklyRoutine).filter(models.WeeklyRoutine.student_id == profile.id)
    )
    routines = routines_result.scalars().all()
    
    day_order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    day_totals = {day: 0 for day in day_order}
    
    day_map = {
        "MON": "MONDAY", "TUE": "TUESDAY", "WED": "WEDNESDAY",
        "THU": "THURSDAY", "FRI": "FRIDAY", "SAT": "SATURDAY", "SUN": "SUNDAY"
    }
    
    for routine in routines:
        day_key = day_map.get(routine.day_of_week, routine.day_of_week)
        if day_key in day_totals and routine.total_minutes:
            day_totals[day_key] += routine.total_minutes
    
    weekly_schedule = [
        schemas.DaySchedule(
            day_of_week=day,
            recommended_minutes=day_totals[day],
            source_type="ROUTINE"
        )
        for day in day_order
    ]
    
    return schemas.TimeSlotResponse.success_res(
        data=schemas.WeeklyScheduleData(weekly_schedule=weekly_schedule),
        message="주간 가용 시간 가이드 조회 성공",
        code=200
    )

@router.post("/missions", response_model=schemas.MissionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_weekly_missions(
    request: Optional[schemas.MissionCreateRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [내 학습 관리] 주간 학습 계획 생성
    """
    
    # 1. 프로필 조회
    profile_result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == current_user_id))
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.MissionCreateResponse.fail_res(message="학생 프로필을 찾을 수 없습니다.", code=404)

    # 2. 루틴 조회
    routines_result = await db.execute(select(models.WeeklyRoutine).filter(models.WeeklyRoutine.student_id == profile.id))
    routines = routines_result.scalars().all()
    
    if not routines:
        return schemas.MissionCreateResponse.fail_res(message="주간 루틴이 등록되지 않았습니다.", code=400)

    # 3. 진단 로그 조회
    diagnosis_logs_result = await db.execute(select(models.DiagnosisLog).filter(models.DiagnosisLog.student_id == profile.id))
    diagnosis_logs = diagnosis_logs_result.scalars().all()

    # 4. 유저 조회
    user_result = await db.execute(select(models.User).filter(models.User.id == current_user_id))
    user = user_result.scalars().first()
    
    # 5. student_data 준비
    student_data = {
        'student_id': str(profile.id),
        'student_name': user.name if user else '학생',
        'school_grade': profile.school_grade,
        'semester': profile.semester,
        'subjects': profile.subjects,
        'cognitive_type': profile.cognitive_type.value,
        'start_date': request.start_date if request else None
    }
    
    # 6. 풀이 습관 텍스트
    if diagnosis_logs:
        solving_habits_text = "\n\n".join([
            f"### {log.subject}\n- 풀이 습관 요약: {log.solution_habit_summary}\n- 감지된 태그: {log.detected_tags}"
            for log in diagnosis_logs
        ])
    else:
        solving_habits_text = "### 풀이 습관 분석 데이터 없음\n이미지 기반 풀이 습관 분석이 제공되지 않았습니다."

    # 7. 주간 스케줄 텍스트
    day_map = {"MON": "월요일", "TUE": "화요일", "WED": "수요일", "THU": "목요일", "FRI": "금요일", "SAT": "토요일", "SUN": "일요일"}
    schedule_by_day = {}
    for routine in routines:
        day_kr = day_map.get(routine.day_of_week, routine.day_of_week)
        if day_kr not in schedule_by_day:
            schedule_by_day[day_kr] = []
        schedule_by_day[day_kr].append(routine)
    
    weekly_schedule_text = ""
    for day_kr in ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]:
        if day_kr in schedule_by_day:
            day_routines = schedule_by_day[day_kr]
            total_min = sum(r.total_minutes or 0 for r in day_routines)
            weekly_schedule_text += f"\n{day_kr}: 총 {total_min}분\n"
            for idx, r in enumerate(day_routines, 1):
                block_info = f"  - 블록{idx}: {r.start_time.strftime('%H:%M')}-{r.end_time.strftime('%H:%M')} ({r.total_minutes}분)"
                if r.block_name:
                    block_info += f" - {r.block_name}"
                weekly_schedule_text += block_info + "\n"

    # 8. AI 계획 생성
    try:
        ai_response = await generate_weekly_plan(
            student_data=student_data,
            solving_habits=solving_habits_text,
            weekly_schedule=weekly_schedule_text
        )
    except Exception as e:
        return schemas.MissionCreateResponse.fail_res(message=f"주간 계획 생성 중 오류: {str(e)}", code=500)
    
    # 9. ✅ 여기서 summary_info 계산!
    summary_info = calculate_weekly_summary(ai_response)
    
    # 10. DB 저장 (7일치 DailyPlan + Task)
    try:
        start_date_str = summary_info['start_date']
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        
        print(f"\n💾 7일치 DailyPlan 생성 시작 (시작일: {start_date})")
        
        # ✅ 7일치 DailyPlan 생성
        daily_plan_map = {}
        
        for day_index, day_plan_data in enumerate(ai_response['weekly_plan']):
            current_date = start_date + timedelta(days=day_index)
            
            new_daily_plan = models.DailyPlan(
                student_id=profile.id,
                plan_date=current_date,
                title=day_plan_data.get('daily_focus', f"{current_date.strftime('%Y-%m-%d')} 학습 계획"),
                target_minutes=day_plan_data.get('total_planned_minutes', 0),
                is_completed=False
            )
            db.add(new_daily_plan)
            await db.flush()
            
            daily_plan_map[current_date] = new_daily_plan.id
            print(f"  📅 {current_date} DailyPlan 생성 (ID: {new_daily_plan.id})")
        
        print(f"✅ {len(daily_plan_map)}개 DailyPlan 생성 완료\n")
        
        # ✅ Task 생성 (각 날짜의 plan_id에 맞게)
        task_id_map = {}
        total_tasks = 0
        
        for day_index, day_plan_data in enumerate(ai_response['weekly_plan']):
            current_date = start_date + timedelta(days=day_index)
            plan_id = daily_plan_map[current_date]
            
            print(f"  📋 {current_date} Task 생성:")
            
            for task_data in day_plan_data['tasks']:
                new_task = models.Task(
                    plan_id=plan_id,
                    category=task_data['category'],
                    title=task_data['title'],
                    assigned_minutes=task_data['assigned_minutes'],
                    is_completed=False,
                    sequence=task_data['sequence']
                )
                db.add(new_task)
                await db.flush()
                
                task_id_map[task_data['sequence']] = new_task.id
                total_tasks += 1
                
                print(f"    ➕ {task_data['title']} ({task_data['assigned_minutes']}분)")
        
        await db.commit()
        print(f"\n✅ 총 {total_tasks}개 Task 저장 완료!")

        # Task ID 매핑
        for day_plan in ai_response['weekly_plan']:
            for task_data in day_plan['tasks']:
                task_data['task_id'] = str(task_id_map.get(task_data['sequence'], uuid.uuid4()))
        
        # 응답 생성
        response_data = schemas.WeeklyPlanData(
            plan_id=daily_plan_map[start_date],
            student_id=profile.id,
            start_date=summary_info['start_date'],
            end_date=summary_info['end_date'],
            total_study_minutes=summary_info['total_study_minutes'],
            subject_distribution=summary_info['subject_distribution'],
            focus_areas=summary_info['focus_areas'],
            weekly_plan=[schemas.DailyPlanDetail(**day_plan) for day_plan in ai_response['weekly_plan']],
            weekly_summary=schemas.WeeklySummaryDetail(**ai_response.get('weekly_summary', {})),
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        
        return schemas.MissionCreateResponse.success_res(
            data=response_data,
            message="주간 학습 계획 생성 성공",
            code=201
        )
        
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        return schemas.MissionCreateResponse.fail_res(
            message=f"계획 저장 중 오류: {str(e)}",
            code=500
        )


@router.get("/dashboard", response_model=schemas.DashboardResponse, status_code=status.HTTP_200_OK)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    profile_result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == current_user_id))
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.DashboardResponse.fail_res(message="학생 프로필을 찾을 수 없습니다.", code=404)
    
    user_result = await db.execute(select(models.User).filter(models.User.id == current_user_id))
    user = user_result.scalars().first()
    
    today = datetime.now()
    today_day_code = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}[today.weekday()]
    
    routines_result = await db.execute(select(models.WeeklyRoutine).filter(
        models.WeeklyRoutine.student_id == profile.id,
        models.WeeklyRoutine.day_of_week == today_day_code
    ))
    today_routines = routines_result.scalars().all()
    
    today_available_minutes = sum(r.total_minutes or 0 for r in today_routines)
    
    response_data = schemas.DashboardSummaryData(
        student_name=user.name if user else "학생",
        streak_days=profile.streak_days,
        today_available_minutes=today_available_minutes,
        today_date=today.strftime("%Y-%m-%d")
    )
    
    return schemas.DashboardResponse.success_res(data=response_data, message="대시보드 요약 조회 성공", code=200)

@router.get("/missions/today", response_model=schemas.TodayMissionResponse, status_code=status.HTTP_200_OK)
async def get_today_mission(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [대시보드] 오늘의 미션 조회 (타임테이블 형식)
    """
    
    print("\n" + "="*60)
    print("🔍 오늘의 미션 조회 디버깅 (Async)")
    print("="*60)
    
    # 1. 학생 프로필 조회
    profile_result = await db.execute(
        select(models.StudentProfile).filter(
            models.StudentProfile.user_id == current_user_id
        )
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.TodayMissionResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다.",
            code=404
        )
    
    print(f"✅ 학생 프로필: {profile.id}")
    
    # 2. 오늘 날짜 및 요일
    today = date.today()
    day_map_reverse = {
        0: "MON", 1: "TUE", 2: "WED", 3: "THU",
        4: "FRI", 5: "SAT", 6: "SUN"
    }
    today_day_code = day_map_reverse[today.weekday()]
    
    print(f"📅 오늘 날짜: {today} ({today_day_code})")
    
    # 3. 오늘 요일의 WeeklyRoutine 조회
    routines_result = await db.execute(
        select(models.WeeklyRoutine).filter(
            models.WeeklyRoutine.student_id == profile.id,
            models.WeeklyRoutine.day_of_week == today_day_code
        ).order_by(models.WeeklyRoutine.start_time)
    )
    today_routines = routines_result.scalars().all()
    
    print(f"📋 오늘 요일({today_day_code})의 루틴 개수: {len(today_routines)}")
    for idx, r in enumerate(today_routines):
        print(f"  루틴 {idx+1}: {r.start_time} ~ {r.end_time} ({r.total_minutes}분)")
    
    # 4. 오늘 날짜의 DailyPlan 조회
    plan_result = await db.execute(
        select(models.DailyPlan).filter(
            models.DailyPlan.student_id == profile.id,
            models.DailyPlan.plan_date == today
        )
    )
    daily_plan = plan_result.scalars().first()
    
    if daily_plan:
        print(f"✅ DailyPlan 발견: {daily_plan.id}, 날짜: {daily_plan.plan_date}, 제목: {daily_plan.title}")
    else:
        print(f"❌ DailyPlan 없음 (오늘: {today})")
        
        # 디버깅: 모든 DailyPlan 조회
        all_plans_result = await db.execute(
            select(models.DailyPlan).filter(
                models.DailyPlan.student_id == profile.id
            )
        )
        all_plans = all_plans_result.scalars().all()
        print(f"   전체 DailyPlan 개수: {len(all_plans)}")
        for p in all_plans:
            print(f"   - plan_date={p.plan_date} (타입: {type(p.plan_date)}), title={p.title}")
    
    # 5. Task 목록 조회
    tasks = []
    if daily_plan:
        tasks_result = await db.execute(
            select(models.Task).filter(
                models.Task.plan_id == daily_plan.id
            ).order_by(models.Task.sequence)
        )
        tasks = tasks_result.scalars().all()
        
        print(f"✅ Task 개수: {len(tasks)}")
        for idx, t in enumerate(tasks):
            print(f"  Task {idx+1}: {t.category} - {t.title} ({t.assigned_minutes}분, seq={t.sequence})")
    else:
        print(f"⚠️  DailyPlan이 없어서 Task를 조회할 수 없음")
    
    # 6. 시간대별 스케줄 생성
    schedule = []
    task_index = 0
    
    if not today_routines:
        print("⚠️  오늘 요일의 WeeklyRoutine이 없어서 스케줄을 생성할 수 없음")
        print("="*60 + "\n")
        
        return schemas.TodayMissionResponse.success_res(
            data=schemas.TodayMissionData(
                mission_date=today.strftime("%Y-%m-%d"),
                mission_title="오늘의 학습 시간표",
                total_minutes=0,
                completion_rate=0.0,
                schedule=[]
            ),
            message="오늘의 미션이 없습니다.",
            code=200
        )
    
    print("\n🔧 스케줄 생성 시작:")
    
    for routine in today_routines:
        # 시간대 생성 (1시간 단위)
        current_time = datetime.combine(today, routine.start_time)
        end_time = datetime.combine(today, routine.end_time)
        
        print(f"\n루틴: {routine.start_time} ~ {routine.end_time}")
        
        while current_time < end_time:
            time_slot_str = current_time.strftime("%H:%M")
            
            # 해당 시간대에 배치할 Task 찾기
            if task_index < len(tasks):
                task = tasks[task_index]
                
                print(f"  {time_slot_str}: [{task.category}] {task.title} ({task.assigned_minutes}분)")
                
                task_item = schemas.ScheduleTaskItem(
                    task_id=task.id,
                    category=task.category,
                    title=task.title,
                    subtitle="클릭하여 완료 표시",
                    assigned_minutes=task.assigned_minutes,
                    is_completed=task.is_completed,
                    status="완료" if task.is_completed else "진행 가능"
                )
                
                task_index += 1
            else:
                # Task가 없으면 "일정 없음"
                print(f"  {time_slot_str}: [일정 없음] 잠김")
                
                task_item = schemas.ScheduleTaskItem(
                    task_id=uuid.uuid4(),
                    category="일정 없음",
                    title="일정 없음",
                    subtitle="나중 분양 선택 중 (1시간)",
                    assigned_minutes=60,
                    is_completed=False,
                    status="잠김"
                )
            
            schedule.append(schemas.TimeSlotSchedule(
                time_slot=time_slot_str,
                task=task_item
            ))
            
            # 다음 시간대로 (1시간 증가)
            current_time += timedelta(hours=1)
    
    print(f"\n✅ 생성된 스케줄 개수: {len(schedule)}")
    
    # 7. 완료율 계산
    if tasks:
        total_task_count = len(tasks)
        completed_task_count = sum(1 for t in tasks if t.is_completed)
        completion_rate = (completed_task_count / total_task_count * 100)
    else:
        completion_rate = 0.0
    
    # 총 목표 시간
    total_minutes = daily_plan.target_minutes if daily_plan else sum(r.total_minutes or 0 for r in today_routines)
    
    print(f"📊 총 목표 시간: {total_minutes}분")
    print(f"📊 완료율: {completion_rate}%")
    print("="*60 + "\n")
    
    # 8. 응답 생성
    response_data = schemas.TodayMissionData(
        mission_date=today.strftime("%Y-%m-%d"),
        mission_title=daily_plan.title if daily_plan else "오늘의 학습 시간표",
        total_minutes=total_minutes,
        completion_rate=round(completion_rate, 1),
        schedule=schedule
    )
    
    return schemas.TodayMissionResponse.success_res(
        data=response_data,
        message="오늘의 학습 시간표 조회 성공",
        code=200
    )

@router.get("/recent-ranking", response_model=schemas.RecentRankingResponse, status_code=status.HTTP_200_OK)
async def get_recent_ranking(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    my_profile_result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == current_user_id))
    my_profile = my_profile_result.scalars().first()
    
    if not my_profile:
        return schemas.RecentRankingResponse.fail_res(message="학생 프로필을 찾을 수 없습니다.", code=404)
    
    same_grade_profiles_result = await db.execute(
        select(
            models.StudentProfile.id,
            models.StudentProfile.user_id,
            models.StudentProfile.total_points
        ).filter(
            models.StudentProfile.school_grade == my_profile.school_grade
        ).order_by(
            models.StudentProfile.total_points.desc()
        ).limit(limit)
    )
    same_grade_profiles = same_grade_profiles_result.all() # .all() for tuples

    my_rank = next((idx for idx, p in enumerate(same_grade_profiles, 1) if p.id == my_profile.id), 0)
    
    if my_rank == 0:
        higher_count_result = await db.execute(
            select(func.count(models.StudentProfile.id)).filter(
                models.StudentProfile.school_grade == my_profile.school_grade,
                models.StudentProfile.total_points > my_profile.total_points
            )
        )
        my_rank = higher_count_result.scalar_one() + 1
    
    recent_activities = []
    user_ids = [p.user_id for p in same_grade_profiles]
    users_result = await db.execute(select(models.User).filter(models.User.id.in_(user_ids)))
    users_map = {str(u.id): u for u in users_result.scalars().all()}

    for idx, p in enumerate(same_grade_profiles, 1):
        user = users_map.get(str(p.user_id))
        display_name = user.name if p.id == my_profile.id and user else (user.name[0] if user and user.name else f"User_{str(p.id)[:8]}")
        
        recent_activities.append(schemas.RecentRankingItem(
            rank=idx, user_id=display_name, points=p.total_points,
            points_change=f"+{p.total_points}pts", is_me=(p.id == my_profile.id)
        ))
    
    response_data = schemas.RecentRankingData(
        my_rank=my_rank, my_points=my_profile.total_points, recent_activities=recent_activities
    )
    
    return schemas.RecentRankingResponse.success_res(data=response_data, message="실시간 랭킹 조회 성공")

@router.get("/learning-stats", response_model=schemas.LearningStatsResponse)
async def get_learning_stats(
    year: Optional[int] = Query(None, description="조회 연도 (YYYY)"),
    month: Optional[int] = Query(None, description="조회 월 (1-12)"),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month

    profile_result = await db.execute(select(models.StudentProfile).filter(models.StudentProfile.user_id == current_user_id))
    profile = profile_result.scalars().first()
    
    if not profile:
        return schemas.LearningStatsResponse.fail_res(message="학생 프로필을 찾을 수 없습니다.", code=404)

    tasks_result = await db.execute(
        select(models.Task).join(models.DailyPlan).filter(
            models.DailyPlan.student_id == profile.id,
            extract('year', models.DailyPlan.plan_date) == target_year,
            extract('month', models.DailyPlan.plan_date) == target_month
        )
    )
    tasks = tasks_result.scalars().all()

    subject_map = {}
    for task in tasks:
        cat = task.category
        if cat not in subject_map: subject_map[cat] = {"total": 0, "completed": 0}
        subject_map[cat]["total"] += 1
        if task.is_completed: subject_map[cat]["completed"] += 1

    subject_stats = []
    for cat, counts in subject_map.items():
        total, completed = counts["total"], counts["completed"]
        achievement_rate = round((completed / total * 100), 1) if total > 0 else 0.0
        subject_stats.append(schemas.SubjectStatItem(
            category=cat, total_count=total, completed_count=completed, achievement_rate=achievement_rate
        ))

    return schemas.LearningStatsResponse.success_res(
        data=schemas.LearningStatsData(subject_stats=subject_stats),
        message=f"{target_year}년 {target_month}월 학습 통계 조회 성공"
    )