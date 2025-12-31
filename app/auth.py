from fastapi import Header, HTTPException
from jose import jwt  # pip install python-jose[cryptography] 필요

def get_current_user_id(authorization: str = Header(None)):
    """
    프론트엔드가 보낸 'Authorization: Bearer {token}' 헤더를 검증합니다.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")
    
    try:
        # 'Bearer ' 문구를 제외하고 토큰만 추출
        token = authorization.replace("Bearer ", "")
        
        # Supabase Secret으로 토큰 해독
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            options={"verify_aud": False}
        )
        
        # 유저의 UUID(id) 반환
        return payload["sub"] 
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")