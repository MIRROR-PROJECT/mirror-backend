import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

async def analyze_solving_habit(image_bytes: bytes, style_answers: list):
    # 1. 이미지를 AI가 읽을 수 있도록 base64 인코딩 (Vision 모델 사용 시 필요)
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    # 2. 프롬프트 구성
    system_prompt = """
    너는 교육 전문가이자 수학 교육 분석가야. 
    학생이 제출한 '풀이 이미지'와 '사전 성향 설문 데이터'를 바탕으로 학생의 공부 습관을 분석해야 해.
    
    분석 시 다음 형식을 반드시 지켜줘:
    1. extracted_content: 학생의 풀이 습관을 2~3문장으로 요약.
    2. detected_tags: 학생의 특징을 잘 나타내는 키워드 2~3개를 리스트 형태로 추출.
    """

    user_prompt = f"""
    [학생 성향 데이터]
    {style_answers} (이 데이터는 학생이 스스로 대답한 평소 습관이야)

    [분석 요청]
    첨부된 이미지(학생의 실제 풀이 과정)를 보고, 성향 데이터와 일치하는지 혹은 어떤 특징이 보이는지 분석해줘.
    한국어로 자연스럽게 답변해줘.
    """

    # 3. Llama API 호출 (Llama 3.2 Vision 모델 권장)
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-11b-vision-instruct:free", # 이미지 분석이 가능한 모델
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        response_format={ "type": "json_object" } # JSON으로 받으면 파싱이 쉬움
    )

    # API 응답 결과 반환 (이후 파싱 로직 추가 필요)
    # 여기서는 예시로 고정된 구조를 반환하지만, 실제로는 response 내용을 파싱합니다.
    return {
        "extracted_content": "풀이 과정이 논리적이나 계산 실수가 잦아보입니다.",
        "detected_tags": ["논리적_전개", "계산_실수"]
    }