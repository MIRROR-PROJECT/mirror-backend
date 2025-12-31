import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
import google.generativeai as genai
from app import schemas
from app.dependencies import get_current_user

router = APIRouter(prefix="/analysis", tags=["Step 3: 이미지 분석"])

# Gemini 설정
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

@router.post("/solving-image", response_model=schemas.BaseResponse)
async def analyze_solving_image(
    file: UploadFile = File(...),
    user_id: str = Form(...), # 명세서에 따라 body로 받음
    current_user_id: str = Depends(get_current_user) # 보안 검증
):
    try:
        # 1. 이미지 읽기
        contents = await file.read()
        
        # 2. Gemini에게 분석 요청 (프롬프트는 서비스 기획에 맞게 수정 가능)
        prompt = """
        이 사진은 학생이 문제를 푼 이미지입니다. 
        1. 학생의 풀이 습관을 한 문장으로 요약하세요.
        2. '식_생략', '계산_실수', '논리적', '직관적' 등 핵심 태그 2개를 뽑으세요.
        형식: 요약 | 태그1, 태그2
        """
        
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": contents}
        ])
        
        # 3. AI 응답 파싱 (임시 로직)
        # 실제로는 정규식이나 더 세밀한 파싱이 필요합니다.
        result_text = response.text
        summary, tags = result_text.split("|") if "|" in result_text else (result_text, "분석중")

        # 4. 성공 응답 (명세서 규격 준수)
        return {
            "success": True,
            "code": 200,
            "message": "이미지 분석 및 데이터 저장 완료",
            "data": {
                "analysis_id": "d1eebc99-9c0b-4ef8-bb6d-6bb9bd380a44", # DB 연동 후 실제 ID 반환
                "extracted_content": summary.strip(),
                "detected_tags": [t.strip() for t in tags.split(",")]
            }
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail="이미지 분석 중 오류가 발생했습니다.")