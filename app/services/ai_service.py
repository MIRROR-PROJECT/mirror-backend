import os
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

async def analyze_solving_habit(image_bytes: bytes, cognitive_type: str, subject: str):
    """
    이미지 1장, 인지 성향, 과목명을 받아 Llama 3.2 Vision으로 분석
    """
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    # 인지 성향별 분석 가이드라인 (AI가 참고할 페르소나 강화)
    type_guide = {
        "SPEED_FIRST": "빠른 직관으로 답을 도출하지만 식 생략과 계산 실수가 잦은 스타일",
        "PRECISION_FIRST": "정교한 식 전개에 집중하느라 시간 배분에 어려움을 겪는 스타일",
        "BURST_STUDY": "집중력 기복이 커서 풀이 후반부로 갈수록 집중도가 흐트러지는 스타일"
    }.get(cognitive_type, "")

    system_prompt = f"""
    # Role: Mirror AI (학습 인지 행동 분석 전문가)
    당신은 학생의 풀이 과정을 관찰하여 뇌과학/심리학적 관점에서 학습 패턴을 진단하는 전문가입니다.

    # Context
    - 분석 과목: {subject}
    - 학생 성향: {cognitive_type} ({type_guide})

    # Task: [이미지 증거 기반 분석]
    제공된 [{subject}] 풀이 이미지를 보고, 학생의 사전 성향인 [{cognitive_type}]이 실제 풀이 행동에서 어떻게 나타나는지 구체적인 '증거'를 찾아 분석하십시오.

    # Analysis Guidelines (세밀한 분석 지침)
    1. **시각적 증거 포착**: 펜의 흔적, 여백 활용 방식, 지문 내 밑줄 습관, 수식 전개 과정의 생략 여부 등을 면밀히 살피십시오.
    2. **성향과의 연결성**: 단순히 '식을 생략함'이라고 하지 말고, '{cognitive_type} 성향 때문에 결과 도출 속도에 치중하여 중간 과정을 생략하는 경향이 이미지에서 확인됨'과 같이 서술하십시오.
    3. **과목 특수성 반영**: {subject} 과목 특유의 풀이 문법(수학의 등호 사용, 국어의 키워드 마킹 등)을 고려하십시오.

    # Response Format (JSON 전용)
    반드시 다음의 한국어 JSON 구조로만 답변하십시오. 다른 설명은 배제하십시오.
    {{
        "extracted_content": "풀이 이미지에서 발견된 핵심 습관을 성향과 연결하여 2~3문장으로 깊이 있게 분석.",
        "detected_tags": ["이미지에서 포착된 핵심 특징 2~3개"]
    }}

    ## Response 예시 (Example)
    성향이 'SPEED_FIRST'이고 과목이 'MATH'인 경우의 응답 예시:
    {{
        "extracted_content": "수식의 중간 과정을 생략하고 암산으로 빠르게 답을 도출하는 'SPEED_FIRST'의 전형적인 특징이 확인됩니다. 특히 복잡한 연산 여백에 정돈되지 않은 계산 흔적이 흩어져 있는 것으로 보아, 검토보다는 직관적 문제 풀이에 치중하는 경향이 이미지상에 뚜렷하게 나타납니다.",
        "detected_tags": ["직관적_추론", "연산_생략", "속도_중심"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free", 
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