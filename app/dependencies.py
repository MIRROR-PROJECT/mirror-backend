import os
from dotenv import load_dotenv
from fastapi import Header, HTTPException, Depends
from jose import jwt
import json

load_dotenv()

# .env에서 보안 키 로드
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    raise RuntimeError("SUPABASE_JWT_SECRET is not set. Put it in .env or export it.")

# 💡 이것이 API 라우터에서 'Depends'로 사용할 의존성 함수입니다.
async def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 헤더 누락")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # 💡 Render에 넣은 JSON 텍스트를 파이썬 딕셔너리로 변환
        jwk_key = json.loads(SUPABASE_JWT_SECRET)
        
        # 💡 변환된 jwk_key를 사용하여 ES256 알고리즘으로 해독
        payload = jwt.decode(
            token, 
            jwk_key, 
            algorithms=["ES256"], 
            options={"verify_aud": False}
        )
        
        user_id = payload.get("sub")
        return user_id
        
    except Exception as e:
        # 에러가 나면 어떤 에러인지 확인할 수 있게 메시지 유지
        raise HTTPException(status_code=401, detail=f"인증 실패: {str(e)}")