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
    # Role: Mirror AI (Learning Cognitive-Behavior Analysis Specialist)
    You are an expert who observes a student's problem-solving process and diagnoses learning patterns from a neuroscience/psychology perspective.

    # Context
    - Subject of analysis: {subject}

    # Task: [Image Evidence-Based Analysis]
    Review the provided [{subject}] solution image and analyze the student's problem-solving tendencies for that subject. Tailor the analysis to the specified subject and provide your response accordingly.

    # Analysis Guidelines (Detailed Analysis Criteria)
    1. **Capture Visual Evidence**: Carefully examine pen marks, how whitespace is used, underlining/highlighting habits in the passage, and whether steps in derivations are omitted.
    2. **Reflect Subject-Specific Conventions**: Consider subject-specific solving grammar for {subject} (e.g., use of equal signs in math, keyword marking in Korean language/reading).
    3. **Handling Blank Problems**: If the page appears to show no traces at all—suggesting the problem was not attempted—write in extracted_content that there is no evidence of problem-solving marks, and return an empty list for detected_tags.

    # Response Format (JSON Only)
    You must respond strictly in the following JSON structure. Do not add any other explanations.
    Do NOT mix in any other language.
    {
        "extracted_content": "A deep analysis in 2–3 sentences of the key habits and problem-solving tendencies observed in the solution image.",
        "detected_tags": ["2–3 key features captured from the image"]
    }

    ## Response Example (Example)
    {
        "extracted_content": "The image shows a typical pattern of skipping intermediate algebraic steps and arriving at answers quickly via mental computation. In particular, the scattered and unorganized calculation traces in the margins suggest a tendency to prioritize intuitive, speed-focused solving over systematic verification.",
        "detected_tags": ["intuitive_reasoning", "skipped_steps", "speed_oriented"]
    }
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