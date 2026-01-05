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
            AI 생성 리포트 컨텐츠 (영어로 반환)
        """

        # 과목별 정보 포맷팅
        subjects_text = "\n".join([
            f"- {s['subject_name']}: 미션 달성률 {s['mission_achievement_rate']}%, 질문 {s['question_count']}회"
            for s in subject_details
        ])

        prompt = f"""
You are an AI tutor who analyzes a student's daily learning.
Based on the study data below, write warm, motivating feedback for the student.

## Today's Study Data
- Total study time: {total_study_time} minutes
- Average achievement rate: {achievement_rate}%
- Total number of questions asked: {question_count}
- Most immersive subject: {most_immersive_subject}

## Subject Details
{subjects_text}

## Output Format (JSON)
Respond ONLY in the following JSON format:
{
    "ai_summary_title": "Summarize today's learning in one sentence (within 20 characters)",
    "ai_good_point": "What you did well today (50–100 characters, specific and warm)",
    "ai_improvement_point": "How you can do even better tomorrow (50–100 characters, encouraging tone)",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "passion_temp": Passion temperature (a number between 36.5 and 100, reflecting study immersion and achievement),
    "subject_badges": [
        {"subject": "Subject name", "badge": "Badge name", "reason": "Reason for the badge"}
    ]
}

## Notes
- Maintain an encouraging and motivating tone for the student.
- Use specific numbers and subject names.
- Passion temperature should reflect overall study time, achievement rate, and number of questions asked.
- Award badges only to the most outstanding subjects (up to 3).
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 학생들을 응원하는 AI 튜터입니다."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            # # 기본값 설정 (혹시 모를 누락 대비)
            # return {
            #     "ai_summary_title": result.get("ai_summary_title", "오늘도 성장한 하루"),
            #     "ai_good_point": result.get("ai_good_point", "꾸준히 학습하는 모습이 멋집니다!"),
            #     "ai_improvement_point": result.get("ai_improvement_point", "내일은 조금 더 깊이 있게 공부해봐요."),
            #     "keywords": result.get("keywords", ["성장", "꾸준함", "노력"]),
            #     "passion_temp": result.get("passion_temp", 50.0),
            #     "subject_badges": result.get("subject_badges", [])
            # }
            # Default values (as a fallback in case anything is missing)
            return {
                "ai_summary_title": result.get("ai_summary_title", "Another day of growth"),
                "ai_good_point": result.get("ai_good_point", "Your consistent studying is awesome!"),
                "ai_improvement_point": result.get("ai_improvement_point", "Tomorrow, try studying a bit more deeply."),
                "keywords": result.get("keywords", ["Growth", "Consistency", "Effort"]),
                "passion_temp": result.get("passion_temp", 50.0),
                "subject_badges": result.get("subject_badges", [])
            }

        except Exception as e:
            raise Exception(f"AI 리포트 생성 실패: {str(e)}")
