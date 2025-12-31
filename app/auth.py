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
    except Exception as e:
        # 에러 원인을 명확히 보기 위해 디버깅 메시지를 포함합니다.
        raise HTTPException(status_code=401, detail=f"인증 실패: {str(e)}")