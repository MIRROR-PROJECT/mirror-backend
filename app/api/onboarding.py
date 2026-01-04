from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
import uuid

from app.database import get_db
from app.models import User, StudentProfile, TeacherProfile, ParentProfile
from app.schemas import (
    RoleSelectionRequest,
    RoleSelectionResponse,
    RoleSelectionData,
    RoleType
)
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"]
)


@router.post(
    "/role",
    response_model=RoleSelectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="사용자 역할 선택 및 저장",
    description="온보딩 과정에서 사용자가 역할(학생/선생님/학부모)을 선택하여 저장합니다."
)
async def select_role(
    request: RoleSelectionRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    역할 선택 API

    - **role**: student, teacher, parent 중 하나
    - 역할에 따라 student_profiles, teacher_profiles, parent_profiles 테이블에 레코드 생성
    - users 테이블의 role 필드 업데이트
    - JWT 토큰 재발급 권장 (role 정보 포함)
    """

    try:
        print(f"🔍 받은 current_user_id: {current_user_id}")
        print(f"🔍 current_user_id 타입: {type(current_user_id)}")
        
        # 0. 현재 사용자 조회
        result = await db.execute(select(User).filter(User.id == current_user_id))
        current_user = result.scalars().first()

        # 🆕 DB에 없으면 자동 생성
        if not current_user:
            print(f"⚠️ DB에 user 없음. 자동 생성 시작...")
            
            current_user = User(
                id=current_user_id,
                email=f"{current_user_id}@temp.com",  # 임시 이메일
                # password_hash는 Supabase Auth가 관리하므로 불필요
            )
            db.add(current_user)
            await db.flush()  # ID 생성을 위해 flush (commit 대신)
            print(f"✅ User 자동 생성 완료: {current_user.id}")

        # 1. 이미 역할이 설정되어 있는지 확인
        if current_user.role is not None and current_user.role != "STUDENT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 역할이 설정되어 있습니다"
            )

        role_id: Optional[uuid.UUID] = None
        role_str = request.role.value

        # 2. 역할에 따라 각 테이블에 레코드 생성
        if request.role == RoleType.STUDENT:
            # student_profiles 테이블에 레코드 생성
            new_student = StudentProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_student)
            await db.flush()  # ID 생성을 위해 flush
            role_id = new_student.id
            print(f"✅ StudentProfile 생성: {role_id}")

        elif request.role == RoleType.TEACHER:
            # teacher_profiles 테이블에 레코드 생성
            new_teacher = TeacherProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_teacher)
            await db.flush()
            role_id = new_teacher.id
            print(f"✅ TeacherProfile 생성: {role_id}")

        elif request.role == RoleType.PARENT:
            # parent_profiles 테이블에 레코드 생성
            new_parent = ParentProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_parent)
            await db.flush()
            role_id = new_parent.id
            print(f"✅ ParentProfile 생성: {role_id}")

        # 3. users 테이블 업데이트
        current_user.role = role_str
        print(f"✅ User role 업데이트: {role_str}")

        # 4. 커밋
        await db.commit()
        await db.refresh(current_user)
        print(f"✅ DB 커밋 완료")

        # 5. 응답 데이터 생성
        response_data = RoleSelectionData(
            user_id=current_user.id,
            role=role_str,
            role_id=role_id
        )

        return RoleSelectionResponse.success_res(
            data=response_data,
            message="역할이 성공적으로 등록되었습니다",
            code=201
        )

    except HTTPException:
        await db.rollback()
        print(f"❌ HTTPException 발생 - 롤백")
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ 예외 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )
