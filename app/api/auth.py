# app/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from ..database import get_db  # app.database → ..database
from ..models import User      # app.models → ..models
from ..dependencies import get_current_user  # app.dependencies → ..dependencies

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


class UserSyncRequest(BaseModel):
    name: str
    email: str


@router.post("/sync-user", status_code=status.HTTP_201_CREATED)
async def sync_user(
    request: UserSyncRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Supabase Auth에서 생성된 사용자를 FastAPI DB에 동기화
    """
    try:
        print(f"🔄 사용자 동기화 시작: {current_user_id}")
        print(f"   - name: {request.name}")
        print(f"   - email: {request.email}")
        
        # 이미 존재하는지 확인
        result = await db.execute(select(User).filter(User.id == current_user_id))
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"⚠️ 이미 존재하는 사용자 - 업데이트 진행")
            # 정보 업데이트 (name, email만)
            existing_user.name = request.name
            existing_user.email = request.email
            await db.commit()
            await db.refresh(existing_user)
            
            return {
                "success": True,
                "message": "사용자 정보가 업데이트되었습니다",
                "user_id": str(existing_user.id)
            }
        
        # 새로 생성
        print(f"✅ 새 사용자 생성 중...")
        new_user = User(
            id=current_user_id,
            email=request.email,
            name=request.name,
            # role은 나중에 /onboarding/role에서 설정
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        print(f"✅ 사용자 동기화 완료: {new_user.id}")
        
        return {
            "success": True,
            "message": "사용자가 동기화되었습니다",
            "user_id": str(new_user.id)
        }
        
    except Exception as e:
        await db.rollback()
        print(f"❌ 동기화 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 동기화 실패: {str(e)}"
        )