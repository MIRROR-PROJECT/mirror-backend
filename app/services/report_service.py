"""
일간 리포트 AI 생성 서비스
"""
import os
from openai import AsyncOpenAI
from typing import Dict, Any, List


class ReportGenerationService:
    """AI 리포트 생성 서비스"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다")
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_report(
        self,
        total_study_time: int,
        achievement_rate: float,
        question_count: int,
        most_immersive_subject: str,
        subject_details: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        학습 데이터를 기반으로 AI 리포트 생성

        Args:
            total_study_time: 총 학습 시간 (분)
            achievement_rate: 평균 성취도 (%)
            question_count: 총 질문 횟수
            most_immersive_subject: 가장 몰입한 과목
            subject_details: 과목별 상세 정보

        Returns:
            AI 생성 리포트 컨텐츠
        """

        # 과목별 정보 포맷팅
        subjects_text = "\n".join([
            f"- {s['subject_name']}: 미션 달성률 {s['mission_achievement_rate']}%, 질문 {s['question_count']}회"
            for s in subject_details
        ])

        prompt = f"""
당신은 학생의 일일 학습을 분석하는 AI 튜터입니다.
아래 학습 데이터를 바탕으로 학생에게 동기부여가 되는 따뜻한 피드백을 작성해주세요.

## 오늘의 학습 데이터
- 총 학습 시간: {total_study_time}분
- 평균 성취도: {achievement_rate}%
- 총 질문 횟수: {question_count}회
- 가장 몰입한 과목: {most_immersive_subject}

## 과목별 상세
{subjects_text}

## 출력 형식 (JSON)
다음 JSON 형식으로만 응답하세요:
{{
    "ai_summary_title": "오늘의 학습을 한 문장으로 요약 (20자 이내)",
    "ai_good_point": "오늘 잘한 점 (50-100자, 구체적이고 따뜻하게)",
    "ai_improvement_point": "내일 더 나아질 수 있는 점 (50-100자, 격려하는 톤으로)",
    "keywords": ["키워드1", "키워드2", "키워드3"],
    "passion_temp": 열정 온도 (36.5-100 사이의 숫자, 학습 몰입도와 성취도 반영),
    "subject_badges": [
        {{"subject": "과목명", "badge": "뱃지명", "reason": "뱃지 이유"}}
    ]
}}

## 주의사항
- 학생을 격려하고 동기부여하는 톤 유지
- 구체적인 숫자와 과목명을 활용
- 열정 온도는 학습 시간, 성취도, 질문 횟수를 종합적으로 반영
- 뱃지는 가장 두드러진 과목에만 부여 (최대 3개)
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 학생들을 응원하는 AI 튜터입니다."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            # 기본값 설정 (혹시 모를 누락 대비)
            return {
                "ai_summary_title": result.get("ai_summary_title", "오늘도 성장한 하루"),
                "ai_good_point": result.get("ai_good_point", "꾸준히 학습하는 모습이 멋집니다!"),
                "ai_improvement_point": result.get("ai_improvement_point", "내일은 조금 더 깊이 있게 공부해봐요."),
                "keywords": result.get("keywords", ["성장", "꾸준함", "노력"]),
                "passion_temp": result.get("passion_temp", 50.0),
                "subject_badges": result.get("subject_badges", [])
            }

        except Exception as e:
            raise Exception(f"AI 리포트 생성 실패: {str(e)}")
