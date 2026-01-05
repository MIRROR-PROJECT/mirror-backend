from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from ..database import get_db
from ..models import User, ParentProfile, StudentProfile
from ..schemas import (
    ParentProfileRequest,
    ParentProfileResponse,
    ParentProfileResponseData,
)
from ..dependencies import get_current_user

router = APIRouter(
    prefix="/parents",
    tags=["parents"]
)

@router.post(
    "/profile",
    response_model=ParentProfileResponse,
    summary="학부모 상세 정보 등록",
    description="학부모의 전화번호와 자녀 정보를 등록합니다."
)
async def update_parent_profile(
    request: ParentProfileRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    학부모 상세 정보 등록

    - **child_name**: 자녀 이름
    - **child_phone**: 자녀 연락처
    - **parent_phone**: 학부모 연락처
    """
    try:
        # 1. User 레코드 찾기
        user_result = await db.execute(
            select(User).filter(User.id == current_user_id)
        )
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

        # 2. ParentProfile 레코드 찾기 또는 생성
        parent_profile_result = await db.execute(
            select(ParentProfile).filter(ParentProfile.user_id == current_user_id)
        )
        parent_profile = parent_profile_result.scalars().first()

        if not parent_profile:
            parent_profile = ParentProfile(
                id=uuid.uuid4(),
                user_id=current_user_id
            )
            db.add(parent_profile)

        # 3. 자녀 이름과 전화번호로 학생 찾기
        print(f"🔍 학생 검색 중: 이름={request.child_name}, 전화번호={request.child_phone}")

        student_user_result = await db.execute(
            select(User).filter(
                and_(
                    User.name == request.child_name,
                    User.phone_number == request.child_phone,
                    User.role == 'STUDENT'
                )
            )
        )
        student_user = student_user_result.scalars().first()

        if not student_user:
            # 디버깅: 비슷한 학생들 찾기
            all_students = await db.execute(
                select(User).filter(User.role == 'STUDENT')
            )
            print(f"❌ 학생을 찾지 못했습니다. DB에 등록된 학생 목록:")
            for s in all_students.scalars().all():
                print(f"  - 이름: {s.name}, 전화번호: {s.phone_number}")

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="자녀(학생)를 찾을 수 없습니다. 이름과 전화번호를 확인해주세요.")
        
        student_profile_result = await db.execute(
            select(StudentProfile).filter(StudentProfile.user_id == student_user.id)
        )
        student_profile = student_profile_result.scalars().first()
        if not student_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="자녀의 학생 프로필을 찾을 수 없습니다.")

        # 4. 정보 업데이트
        user.phone_number = request.parent_phone
        parent_profile.parent_name = user.name # 학부모 이름은 user 테이블의 name 사용
        
        # children_ids가 리스트가 아니면 리스트로 초기화
        if not isinstance(parent_profile.children_ids, list):
            parent_profile.children_ids = []

        # 중복 추가 방지
        if str(student_profile.id) not in parent_profile.children_ids:
            # SQLAlchemy가 변경을 감지하도록 새 리스트를 할당
            new_children_ids = list(parent_profile.children_ids)
            new_children_ids.append(str(student_profile.id))
            parent_profile.children_ids = new_children_ids
        
        db.add(user)
        db.add(parent_profile)
        
        await db.commit()
        await db.refresh(user)
        await db.refresh(parent_profile)

        # 5. 응답 데이터 생성
        response_data = ParentProfileResponseData(
            parent_id=parent_profile.id,
            child_name=request.child_name
        )
        
        return ParentProfileResponse.success_res(
            data=response_data,
            message="학부모 정보가 성공적으로 등록되었습니다"
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
