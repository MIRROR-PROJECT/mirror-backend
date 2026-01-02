from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import base64
import re
import json

load_dotenv()

# 클라이언트 인스턴스화를 함수 외부로 이동하고 AsyncOpenAI 사용
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY") # OpenAI 키로 변경
)

async def analyze_solving_habit(image_bytes: bytes, cognitive_type: str, subject: str):
    """
    이미지 1장, 과목명을 받아 gpt-4o으로 분석
    """
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    system_prompt = f"""
    # Role: Mirror AI (학습 인지 행동 분석 전문가)
    당신은 학생의 풀이 과정을 관찰하여 뇌과학/심리학적 관점에서 학습 패턴을 진단하는 전문가입니다.

    # Context
    - 분석 과목: {subject}

    # Task: [이미지 증거 기반 분석]
    제공된 [{subject}] 풀이 이미지를 보고, 학생의 해당 과목 풀이 성향을 분석하십시오. 특정된 과목에 맞게 분석을 하여 답변을 제공하세요. 

    # Analysis Guidelines (세밀한 분석 지침)
    1. **시각적 증거 포착**: 펜의 흔적, 여백 활용 방식, 지문 내 밑줄 습관, 수식 전개 과정의 생략 여부 등을 면밀히 살피십시오.
    2. **과목 특수성 반영**: {subject} 과목 특유의 풀이 문법(수학의 등호 사용, 국어의 키워드 마킹 등)을 고려하십시오.
    3. **빈 문제 처리**: 만약 문제지에 어떠한 흔적도 없는, 풀지 않은 문제로 보일 경우 문제 풀이 흔적이 없음을 extracted_content에 적어주고, detected_tags는 빈 리스트로 반환하십시오. 

    # Response Format (JSON 전용)
    반드시 다음의 한국어 JSON 구조로만 답변하십시오. 다른 설명은 배제하십시오. 다른 언어를 절대로 섞지마십시오.
    {{
        "extracted_content": "풀이 이미지에서 발견된 핵심 습관과 풀이 성향을 2~3문장으로 깊이 있게 분석.",
        "detected_tags": ["이미지에서 포착된 핵심 특징 2~3개"]
    }}

    ## Response 예시 (Example)
    {{
        "extracted_content": "수식의 중간 과정을 생략하고 암산으로 빠르게 답을 도출하는 전형적인 특징이 확인됩니다. 특히 복잡한 연산 여백에 정돈되지 않은 계산 흔적이 흩어져 있는 것으로 보아, 검토보다는 직관적 문제 풀이에 치중하는 경향이 이미지상에 뚜렷하게 나타납니다.",
        "detected_tags": ["직관적_추론", "연산_생략", "속도_중심"]
    }}
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}
            ]
        )
        
        raw_content = response.choices[0].message.content
        print(f"DEBUG - AI Raw Response: {raw_content}") # <--- 이 줄이 로그에 찍힙니다!

        # JSON만 추출 시도
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        return json.loads(raw_content)

    except Exception as e:
        print(f"AI 분석 실패 상세: {str(e)}")
        # 에러 발생 시 raw_content를 볼 수 있게 추가 로그
        return {"extracted_content": "에러 발생", "detected_tags": [str(e)]}