from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from ..database import get_db
from ..models import User, Student, Teacher, Parent
from ..schemas import (
    RoleSelectionRequest, 
    RoleSelectionResponse,
    RoleSelectionData,
    RoleType
)
from ..auth import get_current_user  # 현재 사용자 인증 의존성 (실제 경로에 맞게 수정 필요)

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
    current_user: User = Depends(get_current_user),  # JWT 토큰에서 사용자 추출
    db: Session = Depends(get_db)
):
    """
    역할 선택 API
    
    - **role**: student, teacher, parent 중 하나
    - 역할에 따라 students, teachers, parents 테이블에 레코드 생성
    - users 테이블의 role 필드 업데이트 및 onboarding_completed = True 설정
    - JWT 토큰 재발급 권장 (role 정보 포함)
    """
    
    try:
        # 1. 이미 역할이 설정되어 있는지 확인
        if current_user.role is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 역할이 설정되어 있습니다"
            )
        
        role_id: Optional[uuid.UUID] = None
        role_str = request.role.value
        
        # 2. 역할에 따라 각 테이블에 레코드 생성
        if request.role == RoleType.STUDENT:
            # students 테이블에 레코드 생성
            new_student = Student(
                id=uuid.uuid4(),
                user_id=current_user.id,
                # 필요한 경우 다른 기본값 설정
            )
            db.add(new_student)
            db.flush()  # ID 생성을 위해 flush
            role_id = new_student.id
            
        elif request.role == RoleType.TEACHER:
            # teachers 테이블에 레코드 생성
            new_teacher = Teacher(
                id=uuid.uuid4(),
                user_id=current_user.id,
                # 필요한 경우 다른 기본값 설정
            )
            db.add(new_teacher)
            db.flush()
            role_id = new_teacher.id
            
        elif request.role == RoleType.PARENT:
            # parents 테이블에 레코드 생성
            new_parent = Parent(
                id=uuid.uuid4(),
                user_id=current_user.id,
                # 필요한 경우 다른 기본값 설정
            )
            db.add(new_parent)
            db.flush()
            role_id = new_parent.id
        
        # 3. users 테이블 업데이트
        current_user.role = role_str
        
        # 4. 커밋
        db.commit()
        db.refresh(current_user)
        
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
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )