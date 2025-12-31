import os
from dotenv import load_dotenv
from fastapi import Header, HTTPException, Depends
from jose import jwt

load_dotenv()

# .env에서 보안 키 로드
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# 💡 이것이 API 라우터에서 'Depends'로 사용할 의존성 함수입니다.
async def get_current_user(authorization: str = Header(None)) -> str:
    """
    HTTP Header에서 토큰을 추출하고 유효성을 검사하여 user_id(sub)를 반환합니다.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="인증 헤더가 누락되었거나 형식이 올바르지 않습니다. (Bearer token 필요)"
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # 토큰 해독 및 검증
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            options={"verify_aud": False}
        )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="토큰에 유저 식별 정보가 없습니다.")
            
        return user_id  # 성공 시 유저 UUID 반환
        
    except Exception as e:
        # 토큰 만료, 변조 등 모든 에러 처리
        raise HTTPException(status_code=401, detail="인증 토큰이 유효하지 않거나 만료되었습니다.")