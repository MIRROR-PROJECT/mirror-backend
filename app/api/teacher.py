from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from uuid import UUID
import uuid

from ..database import get_db
from ..models import (
    User, 
    TeacherProfile, 
    StudentClassMatch, 
    StudentProfile, 
    DailyPlan, 
    Task,
    ChatMessage,
    ProblemAnalysisLog
)
from ..schemas import (
    StudentProgressResponseSimple,
    StudentProgressDataSimple,
    StudentProgressSimple,
    WeaknessAnalysis,
    ClassInfoBasic,
    AddStudentRequest,
    AddStudentResponse,
    AddStudentResponseData,
    TeacherClassListResponse,
    TeacherClassListData,
    TeacherClassItem,
    TeacherProfileRequest,
    TeacherProfileResponse,
    TeacherProfileResponseData,
)

from ..dependencies import get_current_user

router = APIRouter(
    prefix="/teacher",
    tags=["teacher"]
)


@router.post(
    "/profile",
    response_model=TeacherProfileResponse,
    summary="선생님 상세 정보 등록",
    description="선생님의 전화번호와 학원명을 등록합니다."
)
async def update_teacher_profile(
    request: TeacherProfileRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    선생님 상세 정보 등록

    - **phone_number**: 선생님 연락처 (예: 010-1234-5678)
    - **academy_name**: 소속 학원명
    """
    try:
        # 1. User 레코드 찾기
        user_result = await db.execute(
            select(User).filter(User.id == current_user_id)
        )
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

        # 2. TeacherProfile 레코드 찾기 또는 생성
        teacher_profile_result = await db.execute(
            select(TeacherProfile).filter(TeacherProfile.user_id == current_user_id)
        )
        teacher_profile = teacher_profile_result.scalars().first()
        
        if not teacher_profile:
            teacher_profile = TeacherProfile(
                id=uuid.uuid4(),
                user_id=current_user_id,
                academy_name=request.academy_name
            )
            db.add(teacher_profile)
        else:
            teacher_profile.academy_name = request.academy_name
            db.add(teacher_profile)

        # 3. 정보 업데이트
        user.phone_number = request.phone_number
        db.add(user)
        
        await db.commit()
        await db.refresh(user)
        await db.refresh(teacher_profile)

        # 4. 응답 데이터 생성
        response_data = TeacherProfileResponseData(
            teacher_id=teacher_profile.id,
            academy_name=teacher_profile.academy_name
        )
        
        return TeacherProfileResponse.success_res(
            data=response_data,
            message="선생님 정보가 성공적으로 등록되었습니다"
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )


def calculate_progress_trend(current: float, previous: float) -> str:
    """진도율 추세 계산"""
    diff = current - previous
    if diff >= 5:
        return "up"
    elif diff <= -5:
        return "down"
    else:
        return "stable"


async def analyze_student_weakness(
    student_id: UUID,
    days: int,
    db: AsyncSession
) -> WeaknessAnalysis:
    """
    학생 취약점 분석
    
    1. weak_concepts: 오답이 많은 개념
    2. error_patterns: StudentProfile의 error_patterns
    3. struggling_subjects: 과목별 오답률 분석
    4. recent_struggles: 최근 어려움 호소 횟수
    """
    
    start_date = datetime.now().date() - timedelta(days=days - 1)
    
    # 1. 취약한 개념 (ProblemAnalysisLog에서 오답 많은 개념)
    problem_logs_result = await db.execute(
        select(ProblemAnalysisLog)
        .filter(
            and_(
                ProblemAnalysisLog.student_id == student_id,
                ProblemAnalysisLog.is_correct == False,
                ProblemAnalysisLog.solved_at >= datetime.combine(start_date, datetime.min.time())
            )
        )
    )
    problem_logs = problem_logs_result.scalars().all()
    
    # 오답 개념 수집
    all_concepts = []
    for log in problem_logs:
        if log.detected_concepts:
            all_concepts.extend(log.detected_concepts)
    
    # 빈도수 계산 후 상위 5개
    concept_counter = Counter(all_concepts)
    weak_concepts = [concept for concept, _ in concept_counter.most_common(5)]
    
    # 2. 오답 패턴 (StudentProfile에서)
    profile_result = await db.execute(
        select(StudentProfile).filter(StudentProfile.id == student_id)
    )
    profile = profile_result.scalars().first()
    error_patterns = profile.error_patterns if profile and profile.error_patterns else []
    
    # 3. 어려움을 겪는 과목 (과목별 오답률 계산)
    subject_stats = {}
    for log in problem_logs:
        subject = log.subject
        if subject:
            if subject not in subject_stats:
                subject_stats[subject] = {"correct": 0, "incorrect": 0}
            subject_stats[subject]["incorrect"] += 1
    
    # 정답 데이터도 포함
    correct_logs_result = await db.execute(
        select(ProblemAnalysisLog)
        .filter(
            and_(
                ProblemAnalysisLog.student_id == student_id,
                ProblemAnalysisLog.is_correct == True,
                ProblemAnalysisLog.solved_at >= datetime.combine(start_date, datetime.min.time())
            )
        )
    )
    correct_logs = correct_logs_result.scalars().all()
    
    for log in correct_logs:
        subject = log.subject
        if subject:
            if subject not in subject_stats:
                subject_stats[subject] = {"correct": 0, "incorrect": 0}
            subject_stats[subject]["correct"] += 1
    
    # 오답률 50% 이상인 과목
    struggling_subjects = []
    for subject, stats in subject_stats.items():
        total = stats["correct"] + stats["incorrect"]
        if total > 0:
            error_rate = stats["incorrect"] / total
            if error_rate >= 0.5:
                struggling_subjects.append(subject)
    
    # 4. 최근 어려움 호소 횟수 (ChatMessage의 student_sentiment)
    chat_result = await db.execute(
        select(ChatMessage)
        .filter(
            and_(
                ChatMessage.student_id == student_id,
                ChatMessage.role == "assistant",
                ChatMessage.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        )
    )
    chat_messages = chat_result.scalars().all()
    
    recent_struggles = sum(
        1 for msg in chat_messages
        if msg.student_sentiment and ("어려움" in msg.student_sentiment or "혼란" in msg.student_sentiment)
    )
    
    return WeaknessAnalysis(
        weak_concepts=weak_concepts,
        error_patterns=error_patterns,
        struggling_subjects=struggling_subjects,
        recent_struggles=recent_struggles
    )


async def verify_teacher_permission(
    class_id: str,
    current_user_id: str,
    db: AsyncSession
) -> StudentClassMatch:
    """선생님 권한 확인"""
    teacher_result = await db.execute(
        select(TeacherProfile).filter(TeacherProfile.user_id == current_user_id)
    )
    teacher = teacher_result.scalars().first()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="선생님 권한이 필요합니다"
        )
    
    class_match_result = await db.execute(
        select(StudentClassMatch)
        .filter(
            and_(
                StudentClassMatch.id == class_id,
                StudentClassMatch.teacher_id == current_user_id
            )
        )
    )
    class_match = class_match_result.scalars().first()
    
    if not class_match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 반을 찾을 수 없거나 담당 선생님이 아닙니다"
        )
    
    return class_match


@router.get(
    "/classes/{class_id}/students/progress",
    response_model=StudentProgressResponseSimple,
    summary="학생 진도율 및 취약점 조회",
    description="특정 반의 학생들의 학습 진도율과 취약점 분석 정보를 조회합니다."
)
async def get_students_progress_clean(
    class_id: str = Path(..., description="반 ID"),
    days: int = Query(7, description="진도율 계산 기간 (일)", ge=1, le=30),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    학생 진도율 및 취약점 조회
    
    - **class_id**: 반 ID
    - **days**: 진도율 계산 기간 (기본 7일)
    
    Returns:
        - 반 정보
        - 기간
        - 학생별 진도율, 추세, 취약점 분석
    """
    
    try:
        # 1. 선생님 권한 확인
        class_match = await verify_teacher_permission(class_id, current_user_id, db)
        
        # 2. 조회 기간 계산
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # 이전 기간 (추세 계산용)
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=days - 1)
        
        # 3. 해당 반의 모든 학생 조회
        students_result = await db.execute(
            select(StudentClassMatch)
            .options(selectinload(StudentClassMatch.student))
            .filter(
                and_(
                    StudentClassMatch.class_name == class_match.class_name,
                    StudentClassMatch.teacher_id == current_user_id
                )
            )
        )
        class_students = students_result.scalars().all()
        
        if not class_students:
            return StudentProgressResponseSimple.success_res(
                data=StudentProgressDataSimple(
                    class_info=ClassInfoBasic(
                        class_id=class_match.id,
                        class_name=class_match.class_name,
                        academy_name=class_match.academy_name
                    ),
                    period_start=start_date.strftime("%Y-%m-%d"),
                    period_end=end_date.strftime("%Y-%m-%d"),
                    total_students=0,
                    students=[]
                ),
                message="학생 진도율 조회 성공"
            )
        
        # 4. 학생별 정보 수집
        student_items = []
        
        for class_student in class_students:
            student_profile = class_student.student
            
            # 유저 정보 조회
            user_result = await db.execute(
                select(User).filter(User.id == student_profile.user_id)
            )
            user = user_result.scalars().first()
            student_name = user.name if user else "이름 없음"
            phone_number = user.phone_number if user and hasattr(user, 'phone_number') else None
            
            # 프로필 이니셜
            profile_initial = student_name[0] if student_name else "?"
            
            # === 현재 기간 진도율 계산 ===
            daily_plans_result = await db.execute(
                select(DailyPlan.id)
                .filter(
                    and_(
                        DailyPlan.student_id == student_profile.id,
                        DailyPlan.plan_date >= start_date,
                        DailyPlan.plan_date <= end_date
                    )
                )
            )
            plan_ids = [row[0] for row in daily_plans_result.all()]
            
            if plan_ids:
                total_result = await db.execute(
                    select(func.count(Task.id))
                    .filter(Task.plan_id.in_(plan_ids))
                )
                total_missions = total_result.scalar() or 0
                
                completed_result = await db.execute(
                    select(func.count(Task.id))
                    .filter(
                        and_(
                            Task.plan_id.in_(plan_ids),
                            Task.is_completed == True
                        )
                    )
                )
                completed_missions = completed_result.scalar() or 0
                
                current_progress = (
                    (completed_missions / total_missions * 100) 
                    if total_missions > 0 else 0.0
                )
            else:
                current_progress = 0.0
            
            # === 이전 기간 진도율 계산 ===
            prev_plans_result = await db.execute(
                select(DailyPlan.id)
                .filter(
                    and_(
                        DailyPlan.student_id == student_profile.id,
                        DailyPlan.plan_date >= prev_start_date,
                        DailyPlan.plan_date <= prev_end_date
                    )
                )
            )
            prev_plan_ids = [row[0] for row in prev_plans_result.all()]
            
            if prev_plan_ids:
                prev_total_result = await db.execute(
                    select(func.count(Task.id))
                    .filter(Task.plan_id.in_(prev_plan_ids))
                )
                prev_total = prev_total_result.scalar() or 0
                
                prev_completed_result = await db.execute(
                    select(func.count(Task.id))
                    .filter(
                        and_(
                            Task.plan_id.in_(prev_plan_ids),
                            Task.is_completed == True
                        )
                    )
                )
                prev_completed = prev_completed_result.scalar() or 0
                
                previous_progress = (
                    (prev_completed / prev_total * 100) 
                    if prev_total > 0 else 0.0
                )
            else:
                previous_progress = 0.0
            
            # 진도율 추세
            progress_trend = calculate_progress_trend(current_progress, previous_progress)
            
            # 취약점 분석
            weakness = await analyze_student_weakness(student_profile.id, days, db)
            
            # 마지막 활동 시각
            last_chat_result = await db.execute(
                select(ChatMessage.created_at)
                .filter(ChatMessage.student_id == student_profile.id)
                .order_by(desc(ChatMessage.created_at))
                .limit(1)
            )
            last_chat = last_chat_result.scalar()
            last_active_at = last_chat.isoformat() + "Z" if last_chat else None
            
            # 학생 정보 추가
            student_items.append(
                StudentProgressSimple(
                    student_id=student_profile.id,
                    student_name=student_name,
                    phone_number=phone_number,
                    profile_initial=profile_initial,
                    class_label=class_student.class_name,
                    progress_rate=round(current_progress, 1),
                    progress_trend=progress_trend,
                    weakness_analysis=weakness,
                    last_active_at=last_active_at
                )
            )
        
        # 5. 응답 데이터 생성 (정렬은 프론트에서)
        response_data = StudentProgressDataSimple(
            class_info=ClassInfoBasic(
                class_id=class_match.id,
                class_name=class_match.class_name,
                academy_name=class_match.academy_name
            ),
            period_start=start_date.strftime("%Y-%m-%d"),
            period_end=end_date.strftime("%Y-%m-%d"),
            total_students=len(class_students),
            students=student_items
        )
        
        return StudentProgressResponseSimple.success_res(
            data=response_data,
            message="학생 진도율 조회 성공"
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




@router.post(
    "/students",
    response_model=AddStudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="학생 추가",
    description="선생님이 자신의 반에 학생을 추가합니다."
)
async def add_student(
    request: AddStudentRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    학생 추가
    
    - **student_name**: 학생 이름
    - **phone_number**: 전화번호 (010-XXXX-XXXX)
    - **class_name**: 반 이름 (선생님의 기존 반 중 선택)
    - **email**: 이메일 (선택, 없으면 자동 생성)
    - **school_grade**: 학년 (선택, 1-12)
    """
    
    try:
        # 1. 선생님 프로필 확인
        teacher_result = await db.execute(
            select(TeacherProfile).filter(TeacherProfile.user_id == current_user_id)
        )
        teacher = teacher_result.scalars().first()
        
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="선생님 권한이 필요합니다"
            )
        
        # 2. 해당 반이 선생님의 반 목록에 있는지 확인
        class_check_result = await db.execute(
            select(StudentClassMatch)
            .filter(
                and_(
                    StudentClassMatch.teacher_id == current_user_id,
                    StudentClassMatch.class_name == request.class_name
                )
            )
            .limit(1)
        )
        existing_class = class_check_result.scalars().first()
        
        if not existing_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 반을 찾을 수 없습니다. 선생님의 반 목록을 확인해주세요"
            )
        
        academy_name = existing_class.academy_name
        
        # 3. 전화번호로 기존 User 찾기
        user_result = await db.execute(
            select(User).filter(User.phone_number == request.phone_number)
        )
        existing_user = user_result.scalars().first()

        # 4. 기존 User가 있는 경우
        if existing_user:
            # 4-1. StudentProfile 찾기
            profile_result = await db.execute(
                select(StudentProfile).filter(StudentProfile.user_id == existing_user.id)
            )
            existing_profile = profile_result.scalars().first()

            # 4-2. StudentProfile이 없으면 생성
            if not existing_profile:
                existing_profile = StudentProfile(
                    id=uuid.uuid4(),
                    user_id=existing_user.id,
                    school_grade=request.school_grade or existing_user.school_grade if hasattr(existing_user, 'school_grade') else None,
                    semester=None,
                    subjects=[],
                    cognitive_type=None,
                    mastery_map={},
                    error_patterns=[],
                    interaction_style=None,
                    streak_days=0,
                    total_points=0
                )
                db.add(existing_profile)
                await db.flush()

            # 4-3. 이미 해당 반에 있는지 체크
            class_match_result = await db.execute(
                select(StudentClassMatch).filter(
                    and_(
                        StudentClassMatch.student_id == existing_profile.id,
                        StudentClassMatch.class_name == request.class_name,
                        StudentClassMatch.teacher_id == current_user_id
                    )
                )
            )
            existing_class_match = class_match_result.scalars().first()

            if existing_class_match:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 해당 반에 등록된 학생입니다"
                )

            # 4-4. 반에만 추가
            new_class_match = StudentClassMatch(
                id=uuid.uuid4(),
                student_id=existing_profile.id,
                teacher_id=current_user_id,
                class_name=request.class_name,
                academy_name=academy_name,
                class_code=None,
                created_at=datetime.utcnow()
            )
            db.add(new_class_match)
            await db.commit()

            response_data = AddStudentResponseData(
                student_id=existing_profile.id,
                user_id=existing_user.id,
                student_name=existing_user.name,
                phone_number=existing_user.phone_number,
                email=existing_user.email,
                class_name=request.class_name,
                academy_name=academy_name,
                created_at=existing_user.created_at.isoformat() + "Z"
            )

        # 5. 기존 User가 없는 경우 - 새로 생성
        else:
            # 5-1. 이메일 생성
            email = request.email
            if not email:
                phone_cleaned = request.phone_number.replace('-', '')
                email = f"{phone_cleaned}@student.mirror.com"

            # 5-2. 이메일 중복 체크
            email_check_result = await db.execute(
                select(User).filter(User.email == email)
            )
            if email_check_result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 등록된 이메일입니다"
                )

            # 5-3. User 생성
            new_user = User(
                id=uuid.uuid4(),
                email=email,
                name=request.student_name,
                phone_number=request.phone_number,
                role="STUDENT",
                created_at=datetime.utcnow()
            )
            db.add(new_user)
            await db.flush()

            # 5-4. StudentProfile 생성
            new_student_profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=new_user.id,
                school_grade=request.school_grade,
                semester=None,
                subjects=[],
                cognitive_type=None,
                mastery_map={},
                error_patterns=[],
                interaction_style=None,
                streak_days=0,
                total_points=0
            )
            db.add(new_student_profile)
            await db.flush()

            # 5-5. StudentClassMatch 생성
            new_class_match = StudentClassMatch(
                id=uuid.uuid4(),
                student_id=new_student_profile.id,
                teacher_id=current_user_id,
                class_name=request.class_name,
                academy_name=academy_name,
                class_code=None,
                created_at=datetime.utcnow()
            )
            db.add(new_class_match)
            await db.commit()

            # 5-6. 응답 데이터 생성
            response_data = AddStudentResponseData(
                student_id=new_student_profile.id,
                user_id=new_user.id,
                student_name=request.student_name,
                phone_number=request.phone_number,
                email=email,
                class_name=request.class_name,
                academy_name=academy_name,
                created_at=new_user.created_at.isoformat() + "Z"
            )
        
        return AddStudentResponse.success_res(
            data=response_data,
            message="학생 추가 성공"
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )





@router.get(
    "/my-classes",
    response_model=TeacherClassListResponse,
    summary="선생님 반 목록 조회",
    description="선생님이 담당하는 반 목록을 조회합니다."
)
async def get_my_classes(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    선생님 반 목록 조회
    
    Returns:
        - 전체 반 수
        - 반별 정보 (반 이름, 학원, 학생 수)
    """
    
    try:
        # 1. 선생님 프로필 확인
        teacher_result = await db.execute(
            select(TeacherProfile).filter(TeacherProfile.user_id == current_user_id)
        )
        teacher = teacher_result.scalars().first()
        
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="선생님 권한이 필요합니다"
            )
        
        # 2. 선생님의 모든 StudentClassMatch 조회
        matches_result = await db.execute(
            select(StudentClassMatch)
            .filter(StudentClassMatch.teacher_id == current_user_id)
        )
        all_matches = matches_result.scalars().all()
        
        # 반이 없는 경우
        if not all_matches:
            return TeacherClassListResponse.success_res(
                data=TeacherClassListData(
                    total_classes=0,
                    classes=[]
                ),
                message="반 목록 조회 성공"
            )
        
        # 3. 반별로 그룹핑 (class_name 기준)
        class_groups = defaultdict(list)
        
        for match in all_matches:
            class_groups[match.class_name].append(match)
        
        # 4. 반 목록 생성
        class_items = []
        
        for class_name, matches in class_groups.items():
            # 첫 번째 match의 정보 사용 (반 대표 ID, 학원 이름)
            first_match = matches[0]
            
            class_items.append(
                TeacherClassItem(
                    class_id=first_match.id,
                    class_name=class_name,
                    academy_name=first_match.academy_name,
                    student_count=len(matches)  # 해당 반의 학생 수
                )
            )
        
        # 5. 반 이름순 정렬
        class_items.sort(key=lambda x: x.class_name)
        
        # 6. 응답 데이터 생성
        response_data = TeacherClassListData(
            total_classes=len(class_items),
            classes=class_items
        )
        
        return TeacherClassListResponse.success_res(
            data=response_data,
            message="반 목록 조회 성공"
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
