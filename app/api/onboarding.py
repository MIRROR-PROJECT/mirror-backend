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


@router.post("/role")
async def select_role(
    request: RoleSelectionRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        print("=" * 50)
        print("🚀 역할 선택 API 시작")
        print("=" * 50)
        print(f"🔍 받은 current_user_id: {current_user_id}")
        print(f"🔍 current_user_id 타입: {type(current_user_id)}")
        print(f"📝 요청된 역할: {request.role.value}")
        
        # 🔍 DB에 있는 모든 user 확인 (디버깅용)
        all_users_result = await db.execute(select(User))
        all_users = all_users_result.scalars().all()
        print(f"\n📊 DB의 총 user 수: {len(all_users)}")
        for idx, user in enumerate(all_users[:5], 1):  # 최대 5개만 출력
            print(f"  {idx}. ID: {user.id} | Email: {user.email} | Name: {user.name} | Role: {user.role}")
        if len(all_users) > 5:
            print(f"  ... 외 {len(all_users) - 5}개")
        
        # 찾으려는 user_id가 DB에 존재하는지 확인
        all_user_ids = [str(u.id) for u in all_users]
        print(f"\n❓ 찾으려는 user_id가 DB에 존재? {current_user_id in all_user_ids}")
        
        # 0. 현재 사용자 조회
        print(f"\n🔎 User 조회 시작: User.id == {current_user_id}")
        result = await db.execute(select(User).filter(User.id == current_user_id))
        current_user = result.scalars().first()
        
        if current_user:
            print(f"✅ User 조회 성공!")
            print(f"   - ID: {current_user.id}")
            print(f"   - Email: {current_user.email}")
            print(f"   - Name: {current_user.name}")
            print(f"   - Role: {current_user.role}")
        else:
            print(f"❌ User 조회 실패 - DB에 존재하지 않음")
        
        # 🆕 User가 없으면 에러 (프론트엔드가 먼저 생성해야 함)
        if not current_user:
            print(f"\n🚫 404 에러 발생: 사용자를 찾을 수 없습니다")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다. 먼저 회원가입을 완료해주세요."
            )
        
        # 1. 이미 역할이 설정되어 있는지 확인 (User.role + 실제 프로필 테이블)
        print(f"\n🔒 역할 중복 확인 중...")
        print(f"   User.role: {current_user.role}")

        # 실제 프로필 테이블 확인
        teacher_check = await db.execute(
            select(TeacherProfile).filter(TeacherProfile.user_id == current_user.id)
        )
        existing_teacher = teacher_check.scalars().first()

        parent_check = await db.execute(
            select(ParentProfile).filter(ParentProfile.user_id == current_user.id)
        )
        existing_parent = parent_check.scalars().first()

        student_check = await db.execute(
            select(StudentProfile).filter(StudentProfile.user_id == current_user.id)
        )
        existing_student = student_check.scalars().first()

        print(f"   TeacherProfile 존재: {existing_teacher is not None}")
        print(f"   ParentProfile 존재: {existing_parent is not None}")
        print(f"   StudentProfile 존재: {existing_student is not None}")

        # Teacher 역할 요청 시 이미 TeacherProfile이 있으면 User.role 동기화 후 반환
        if request.role == RoleType.TEACHER and existing_teacher:
            print(f"⚠️  이미 TeacherProfile 존재 - User.role 동기화 후 기존 프로필 반환")
            if current_user.role != "teacher":
                current_user.role = "teacher"
                await db.commit()
                print(f"✅ User.role을 'teacher'로 동기화 완료")

            return RoleSelectionResponse.success_res(
                data=RoleSelectionData(
                    user_id=current_user.id,
                    role="teacher",
                    role_id=existing_teacher.id
                ),
                message="이미 선생님 프로필이 존재합니다",
                code=200
            )

        # Parent 역할 요청 시 이미 ParentProfile이 있으면 User.role 동기화 후 반환
        if request.role == RoleType.PARENT and existing_parent:
            print(f"⚠️  이미 ParentProfile 존재 - User.role 동기화 후 기존 프로필 반환")
            if current_user.role != "parent":
                current_user.role = "parent"
                await db.commit()
                print(f"✅ User.role을 'parent'로 동기화 완료")

            return RoleSelectionResponse.success_res(
                data=RoleSelectionData(
                    user_id=current_user.id,
                    role="parent",
                    role_id=existing_parent.id
                ),
                message="이미 학부모 프로필이 존재합니다",
                code=200
            )

        # Student는 다중 허용 (여러 클래스 가능)

        print(f"✅ 역할 중복 없음 - 새 프로필 생성 진행")
        
        role_id = None
        role_str = request.role.value
        
        # 2. 역할에 따라 각 테이블에 레코드 생성
        print(f"\n📝 역할별 프로필 생성 시작: {role_str}")
        
        if request.role == RoleType.STUDENT:
            print(f"👨‍🎓 StudentProfile 생성 중...")
            new_student = StudentProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_student)
            await db.flush()
            role_id = new_student.id
            print(f"✅ StudentProfile 생성 완료: {role_id}")
            
        elif request.role == RoleType.TEACHER:
            print(f"👨‍🏫 TeacherProfile 생성 중...")
            new_teacher = TeacherProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_teacher)
            await db.flush()
            role_id = new_teacher.id
            print(f"✅ TeacherProfile 생성 완료: {role_id}")
            
        elif request.role == RoleType.PARENT:
            print(f"👨‍👩‍👧 ParentProfile 생성 중...")
            new_parent = ParentProfile(
                id=uuid.uuid4(),
                user_id=current_user.id,
            )
            db.add(new_parent)
            await db.flush()
            role_id = new_parent.id
            print(f"✅ ParentProfile 생성 완료: {role_id}")
        
        # 3. users 테이블의 role만 업데이트 (name은 건드리지 않음!)
        print(f"\n🔄 User 테이블 role 업데이트 중...")
        print(f"   변경 전: {current_user.role}")
        current_user.role = role_str
        print(f"   변경 후: {current_user.role}")
        
        # 4. 커밋
        print(f"\n💾 DB 커밋 시작...")
        await db.commit()
        print(f"✅ DB 커밋 완료")
        
        await db.refresh(current_user)
        print(f"🔄 User 객체 새로고침 완료")
        
        # 5. 응답
        print(f"\n📦 응답 데이터 생성 중...")
        response_data = RoleSelectionData(
            user_id=current_user.id,
            role=role_str,
            role_id=role_id
        )
        print(f"   - user_id: {response_data.user_id}")
        print(f"   - role: {response_data.role}")
        print(f"   - role_id: {response_data.role_id}")
        
        print(f"\n🎉 역할 선택 API 성공!")
        print("=" * 50)
        
        return RoleSelectionResponse.success_res(
            data=response_data,
            message="역할이 성공적으로 등록되었습니다",
            code=201
        )
        
    except HTTPException as http_exc:
        print(f"\n⚠️ HTTPException 발생")
        print(f"   상태 코드: {http_exc.status_code}")
        print(f"   상세 메시지: {http_exc.detail}")
        await db.rollback()
        print(f"🔙 DB 롤백 완료")
        print("=" * 50)
        raise
        
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러 발생!")
        print(f"   에러 타입: {type(e).__name__}")
        print(f"   에러 메시지: {str(e)}")
        import traceback
        print(f"\n📋 전체 스택 트레이스:")
        print(traceback.format_exc())
        await db.rollback()
        print(f"🔙 DB 롤백 완료")
        print("=" * 50)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )