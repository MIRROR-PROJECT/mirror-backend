"""
AI 튜터 응답 생성 서비스
services/ai_tutor.py
"""
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
from typing import Optional, Dict, Any
import json


load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY") # OpenAI 키로 변경
)

async def generate_tutor_response(
    user_message: str,
    student_context: Dict[str, Any],
    problem_context: Optional[Dict[str, Any]] = None,
    chat_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    AI 튜터 응답 생성
    
    Args:
        user_message: 학생의 질문
        student_context: 학생 정보 (이름, 학년, 인지 유형, 풀이 습관 등)
        problem_context: 특정 문제 관련 컨텍스트 (선택)
        chat_history: 최근 대화 내역 (선택)
    
    Returns:
        {
            "assistant_message": "AI 응답",
            "student_sentiment": {
                "understanding_level": "상/중/하",
                "emotional_state": "긍정적/중립적/부정적/좌절감",
                "engagement_level": "높음/보통/낮음",
                "confusion_points": ["개념1", "개념2"],
                "question_type": "개념질문/풀이질문/확인질문/심화질문",
                "learning_signal": "이해함/이해중/혼란/어려움/관심",
                "needs_intervention": true/false,
                "confidence_score": 0-100
            }
        }
    """
    
    # 시스템 프롬프트 구성
    system_prompt = f"""당신은 학생 '{student_context['student_name']}'을 돕는 AI 튜터입니다.

## 학생 정보
- 이름: {student_context['student_name']}
- 학년: {student_context.get('school_grade', '정보 없음')}학년
- 학기: {student_context.get('semester', '정보 없음')}학기
- 인지 유형: {student_context.get('cognitive_type', '정보 없음')}

## 튜터 역할
1. 학생의 질문에 친절하고 명확하게 답변하세요
2. 단계별로 설명하여 이해를 돕습니다
3. 학생이 스스로 생각할 수 있도록 유도하세요
4. 긍정적이고 격려하는 톤을 유지하세요
"""

    # 문제 컨텍스트 추가
    if problem_context:
        system_prompt += f"""

## 현재 다루는 문제
- 과목: {problem_context.get('subject', '정보 없음')}
- 개념: {', '.join(problem_context.get('detected_concepts', []))}
- 난이도: {problem_context.get('difficulty_level', '정보 없음')}
- 문제 내용: {problem_context.get('extracted_text', '정보 없음')}
"""

    # 대화 내역 구성
    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    if chat_history:
        for msg in chat_history[-5:]:  # 최근 5개만
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # 현재 질문 추가
    messages.append({
        "role": "user",
        "content": user_message
    })

    # API 호출
    try:
        # 1. 튜터 응답 생성
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=messages
        )
        
        assistant_message = response.choices[0].message.content
        
        # 2. 학생 상태 상세 분석
        analysis_prompt = f"""학생의 질문을 분석하여 학습 상태를 평가하세요.

질문: "{user_message}"

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "understanding_level": "상/중/하 중 하나",
  "emotional_state": "긍정적/중립적/부정적/좌절감 중 하나",
  "engagement_level": "높음/보통/낮음 중 하나",
  "confusion_points": ["혼란스러워하는 개념들의 배열"],
  "question_type": "개념질문/풀이질문/확인질문/심화질문 중 하나",
  "learning_signal": "이해함/이해중/혼란/어려움/관심 중 하나",
  "needs_intervention": true 또는 false,
  "confidence_score": 0-100 사이의 숫자
}}

평가 기준:
- understanding_level: 질문의 깊이와 명확성으로 판단
- emotional_state: 질문의 어조와 표현으로 판단
- engagement_level: 질문의 구체성과 적극성으로 판단
- confusion_points: 질문에서 드러나는 불확실한 개념들
- question_type: 질문의 성격 분류
- learning_signal: 전반적인 학습 상태
- needs_intervention: 교사의 직접 도움이 필요한지 여부
- confidence_score: 학생의 자신감 수준 (0=전혀 없음, 100=매우 높음)
"""

        sentiment_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        # JSON 파싱
        sentiment_text = sentiment_response.choices[0].message.content.strip()
        
        # ```json ... ``` 제거
        if sentiment_text.startswith("```"):
            sentiment_text = sentiment_text.split("```")[1]
            if sentiment_text.startswith("json"):
                sentiment_text = sentiment_text[4:]
            sentiment_text = sentiment_text.strip()
        
        student_sentiment = json.loads(sentiment_text)
        
        return {
            "assistant_message": assistant_message,
            "student_sentiment": student_sentiment
        }
        
    except Exception as e:
        print(f"AI 응답 생성 실패: {str(e)}")
        raise


def get_fallback_response() -> Dict[str, Any]:
    """AI API 실패 시 사용할 기본 응답"""
    return {
        "assistant_message": "죄송합니다. 일시적인 오류로 응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
        "student_sentiment": {
            "understanding_level": "중",
            "emotional_state": "중립적",
            "engagement_level": "보통",
            "confusion_points": [],
            "question_type": "개념질문",
            "learning_signal": "이해중",
            "needs_intervention": False,
            "confidence_score": 50.0
        }
    }