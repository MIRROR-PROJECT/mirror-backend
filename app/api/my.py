from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime, timedelta, date

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.weekly_plan_service import generate_weekly_plan, calculate_weekly_summary

router = APIRouter(prefix="/my", tags=["My"])


@router.get("/time-slots", response_model=schemas.TimeSlotResponse)
def get_student_time_slots(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    학생의 주간 가용 시간 가이드 조회
    - WeeklyRoutine 테이블에서 요일별 루틴을 조회하여 권장 학습 시간을 계산합니다.
    """

    # current_user_id로 StudentProfile 조회 (user_id로 찾음!)
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user_id
    ).first()
    
    if not profile:
        return schemas.TimeSlotResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다. 먼저 프로필을 생성해주세요.",
            code=404
        )
    
    # 디버깅
    print(f"Debug - profile.id: {profile.id}, user_id: {current_user_id}")
    
    # 2. 주간 루틴 조회 (profile.id 사용!)
    routines = db.query(models.WeeklyRoutine).filter(
        models.WeeklyRoutine.student_id == profile.id
    ).all()
    
    # 3. 요일별로 그룹화하여 총 시간 계산
    day_order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    day_totals = {day: 0 for day in day_order}
    
    for routine in routines:
        # day_of_week가 "MON", "TUE" 형식이면 변환 필요
        day_map = {
            "MON": "MONDAY",
            "TUE": "TUESDAY", 
            "WED": "WEDNESDAY",
            "THU": "THURSDAY",
            "FRI": "FRIDAY",
            "SAT": "SATURDAY",
            "SUN": "SUNDAY"
        }
        
        # 이미 MONDAY 형식이면 그대로, MON 형식이면 변환
        day_key = day_map.get(routine.day_of_week, routine.day_of_week)
        
        if day_key in day_totals and routine.total_minutes:
            day_totals[day_key] += routine.total_minutes
    
    # 4. 응답 데이터 생성
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
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [내 학습 관리] 주간 학습 계획 생성
    - 학생의 인지 유형, 풀이 습관, 가용 시간을 분석하여 AI가 맞춤형 주간 계획을 생성합니다.
    """
    
    print("\n" + "="*60)
    print("📋 주간 학습 계획 생성 시작")
    print("="*60)
    
    # 1. 학생 프로필 조회
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user_id
    ).first()
    
    if not profile:
        return schemas.MissionCreateResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다. 먼저 프로필을 생성해주세요.",
            code=404
        )
    
    print(f"✅ 학생 프로필 발견: {profile.id}")
    
    # 2. 주간 루틴 확인
    routines = db.query(models.WeeklyRoutine).filter(
        models.WeeklyRoutine.student_id == profile.id
    ).all()
    
    if not routines:
        return schemas.MissionCreateResponse.fail_res(
            message="주간 루틴이 등록되지 않았습니다. 먼저 루틴을 설정해주세요.",
            code=400
        )
    
    print(f"✅ 주간 루틴 발견: {len(routines)}개 블록")
    
    # 3. 풀이 습관 분석 데이터 확인
    diagnosis_logs = db.query(models.DiagnosisLog).filter(
        models.DiagnosisLog.student_id == profile.id
    ).all()
    
    if not diagnosis_logs:
        return schemas.MissionCreateResponse.fail_res(
            message="풀이 습관 분석 데이터가 없습니다. 먼저 초기 진단을 완료해주세요.",
            code=400
        )
    
    print(f"✅ 풀이 습관 분석 데이터 발견: {len(diagnosis_logs)}개 과목")
    
    # 4. 데이터 준비
    # 4-1. 학생 기본 정보
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    student_data = {
        'student_id': str(profile.id),
        'student_name': user.name if user else '학생',
        'school_grade': profile.school_grade,
        'semester': profile.semester,
        'subjects': profile.subjects,
        'cognitive_type': profile.cognitive_type.value,
        'start_date': request.start_date if request else None
    }
    
    # 4-2. 풀이 습관 분석 텍스트 생성
    solving_habits_text = "\n\n".join([
        f"### {log.subject}\n"
        f"- 풀이 습관 요약: {log.solution_habit_summary}\n"
        f"- 감지된 태그: {log.detected_tags}"
        for log in diagnosis_logs
    ])
    
    # 4-3. 주간 스케줄 텍스트 생성
    day_map = {
        "MON": "월요일", "TUE": "화요일", "WED": "수요일",
        "THU": "목요일", "FRI": "금요일", "SAT": "토요일", "SUN": "일요일"
    }
    
    # 요일별로 그룹화
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
    
    print("\n📊 데이터 준비 완료")
    print(f"  - 인지 유형: {student_data['cognitive_type']}")
    print(f"  - 분석된 과목: {len(diagnosis_logs)}개")
    print(f"  - 루틴 블록: {len(routines)}개")
    
    # 5. AI로 주간 계획 생성
    try:
        print("\n🤖 AI 주간 계획 생성 중...")
        ai_response = await generate_weekly_plan(
            student_data=student_data,
            solving_habits=solving_habits_text,
            weekly_schedule=weekly_schedule_text
        )
        
        print("✅ AI 계획 생성 완료!")
        
    except Exception as e:
        print(f"❌ AI 생성 실패: {str(e)}")
        return schemas.MissionCreateResponse.fail_res(
            message=f"주간 계획 생성 중 오류가 발생했습니다: {str(e)}",
            code=500
        )
    
    # 6. 요약 정보 계산
    summary_info = calculate_weekly_summary(ai_response)
    
    # 7. DB에 저장
    try:
        print("\n💾 데이터베이스 저장 중...")
        
        # 시작 날짜 파싱
        start_date_str = summary_info['start_date']
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        
        # DailyPlan 생성 (주간 단위로 하나만 생성)
        new_daily_plan = models.DailyPlan(
            student_id=profile.id,
            plan_date=start_date,
            title=f"{start_date_str} 주간 학습 계획",
            target_minutes=summary_info['total_study_minutes'],
            is_completed=False
        )
        db.add(new_daily_plan)
        db.flush()  # ID 생성
        
        plan_id = new_daily_plan.id
        
        # Task 저장
        task_id_map = {}  # sequence -> UUID 매핑
        for day_plan in ai_response['weekly_plan']:
            for task_data in day_plan['tasks']:
                new_task = models.Task(
                    plan_id=plan_id,
                    category=task_data['category'],
                    title=task_data['title'],
                    assigned_minutes=task_data['assigned_minutes'],
                    is_completed=False,
                    sequence=task_data['sequence']
                )
                db.add(new_task)
                db.flush()
                
                # task_id 매핑 저장
                task_id_map[task_data['sequence']] = new_task.id
        
        db.commit()
        print(f"✅ 데이터베이스 저장 완료! (Plan ID: {plan_id})")
        
        # 8. 응답 데이터 생성
        # AI 응답에 UUID 추가
        for day_plan in ai_response['weekly_plan']:
            for task_data in day_plan['tasks']:
                task_data['task_id'] = str(task_id_map.get(task_data['sequence'], uuid.uuid4()))
        
        response_data = schemas.WeeklyPlanData(
            plan_id=plan_id,
            student_id=profile.id,
            start_date=summary_info['start_date'],
            end_date=summary_info['end_date'],
            total_study_minutes=summary_info['total_study_minutes'],
            subject_distribution=summary_info['subject_distribution'],
            focus_areas=summary_info['focus_areas'],
            weekly_plan=[
                schemas.DailyPlanDetail(**day_plan)
                for day_plan in ai_response['weekly_plan']
            ],
            weekly_summary=schemas.WeeklySummaryDetail(**ai_response.get('weekly_summary', {
                'expected_improvement': '계획 완수 시 실력 향상 예상',
                'adaptive_notes': f'{student_data["cognitive_type"]} 유형에 맞춘 계획',
                'weekly_goals': summary_info['focus_areas']
            })),
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        
        print("\n🎉 주간 학습 계획 생성 완료!")
        print("="*60 + "\n")
        
        return schemas.MissionCreateResponse.success_res(
            data=response_data,
            message="주간 학습 계획 생성 성공",
            code=201
        )
        
    except Exception as e:
        db.rollback()
        print(f"❌ 데이터베이스 저장 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return schemas.MissionCreateResponse.fail_res(
            message=f"계획 저장 중 오류가 발생했습니다: {str(e)}",
            code=500
        )

@router.get("/dashboard", response_model=schemas.DashboardResponse, status_code=status.HTTP_200_OK)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [대시보드] 요약 정보 조회
    - 학생 이름, 스트릭, 오늘 가용 시간
    """
    
    # 1. 학생 프로필 조회
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user_id
    ).first()
    
    if not profile:
        return schemas.DashboardResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다.",
            code=404
        )
    
    # 2. 유저 정보 조회
    user = db.query(models.User).filter(
        models.User.id == current_user_id
    ).first()
    
    # 3. 오늘 가용 시간 계산
    today = datetime.now()
    day_map_reverse = {
        0: "MON", 1: "TUE", 2: "WED", 3: "THU", 
        4: "FRI", 5: "SAT", 6: "SUN"
    }
    today_day_code = day_map_reverse[today.weekday()]
    
    today_routines = db.query(models.WeeklyRoutine).filter(
        models.WeeklyRoutine.student_id == profile.id,
        models.WeeklyRoutine.day_of_week == today_day_code
    ).all()
    
    today_available_minutes = sum(r.total_minutes or 0 for r in today_routines)
    
    # 4. 응답 생성
    response_data = schemas.DashboardSummaryData(
        student_name=user.name if user else "학생",
        streak_days=profile.streak_days,
        today_available_minutes=today_available_minutes,
        today_date=today.strftime("%Y-%m-%d")
    )
    
    return schemas.DashboardResponse.success_res(
        data=response_data,
        message="대시보드 요약 조회 성공",
        code=200
    )

@router.get("/missions/today", response_model=schemas.TodayMissionResponse, status_code=status.HTTP_200_OK)
def get_today_mission(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    [대시보드] 오늘의 미션 조회
    - 오늘 날짜에 해당하는 DailyPlan과 Task 목록
    """
    
    # 1. 학생 프로필 조회
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user_id
    ).first()
    
    if not profile:
        return schemas.TodayMissionResponse.fail_res(
            message="학생 프로필을 찾을 수 없습니다.",
            code=404
        )
    
    # 2. 오늘 날짜의 DailyPlan 조회
    today = date.today()
    daily_plan = db.query(models.DailyPlan).filter(
        models.DailyPlan.student_id == profile.id,
        models.DailyPlan.plan_date == today
    ).first()
    
    # 3. 미션이 없는 경우
    if not daily_plan:
        return schemas.TodayMissionResponse.success_res(
            data=schemas.TodayMissionData(
                mission_date=today.strftime("%Y-%m-%d"),
                mission_title=None,
                total_minutes=0,
                completed_minutes=0,
                completion_rate=0.0,
                tasks=[]
            ),
            message="오늘의 미션이 없습니다.",
            code=200
        )
    
    # 4. Task 목록 조회 (sequence 순서대로)
    tasks = db.query(models.Task).filter(
        models.Task.plan_id == daily_plan.id
    ).order_by(models.Task.sequence).all()
    
    # 5. 완료율 계산 (체크리스트 기반)
    total_task_count = len(tasks)
    completed_task_count = sum(1 for t in tasks if t.is_completed)
    completion_rate = (completed_task_count / total_task_count * 100) if total_task_count > 0 else 0.0
    
    # 총 목표 시간
    total_minutes = daily_plan.target_minutes or sum(t.assigned_minutes for t in tasks)
    
    # 6. 응답 데이터 생성
    task_items = [
        schemas.TodayTaskItem(
            task_id=task.id,
            category=task.category,
            title=task.title,
            assigned_minutes=task.assigned_minutes,
            is_completed=task.is_completed
        )
        for task in tasks
    ]
    
    response_data = schemas.TodayMissionData(
        mission_date=today.strftime("%Y-%m-%d"),
        mission_title=daily_plan.title,
        total_minutes=total_minutes,
        completed_minutes=completed_minutes,
        completion_rate=round(completion_rate, 1),
        tasks=task_items
    )
    
    return schemas.TodayMissionResponse.success_res(
        data=response_data,
        message="오늘의 미션 조회 성공",
        code=200
    )
