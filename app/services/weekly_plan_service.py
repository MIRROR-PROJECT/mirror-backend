"""
주간 학습 계획 생성 AI 서비스 (GPT-4o)
"""
from openai import AsyncOpenAI
import os
import json
from typing import Dict, Any
from datetime import datetime, timedelta


async def generate_weekly_plan(
    student_data: Dict[str, Any],
    solving_habits: str,
    weekly_schedule: str
) -> Dict[str, Any]:
    """
    OpenAI GPT-4o API를 호출하여 주간 학습 계획 생성
    
    Args:
        student_data: 학생 기본 정보
        solving_habits: 과목별 풀이 습관 분석 텍스트
        weekly_schedule: 요일별 가용 시간 텍스트
        
    Returns:
        생성된 주간 계획 JSON
    """
    
    # 프롬프트 생성
    prompt = _build_prompt(student_data, solving_habits, weekly_schedule)
    
    # OpenAI 클라이언트 생성
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    try:
        # GPT-4o API 호출
        response = await client.chat.completions.create(
            model="gpt-4o",  # 또는 "gpt-4o-mini"
            messages=[
                {
                    "role": "system",
                    "content": "당신은 학생 개개인의 학습 스타일을 분석하여 최적화된 주간 학습 계획을 생성하는 전문 AI 튜터입니다. 반드시 순수 JSON 형식으로만 응답하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=8000,
            response_format={"type": "json_object"}  # JSON 모드 강제
        )
        
        # 응답에서 JSON 추출
        response_text = response.choices[0].message.content
        
        # JSON 파싱 (```json ``` 마크다운 제거 - 혹시 모를 경우 대비)
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0].strip()
        
        weekly_plan = json.loads(json_text)
        return weekly_plan
        
    except Exception as e:
        print(f"❌ OpenAI API 호출 실패: {str(e)}")
        raise Exception(f"주간 계획 생성 실패: {str(e)}")


def _build_prompt(
    student_data: Dict[str, Any],
    solving_habits: str,
    weekly_schedule: str
) -> str:
    """프롬프트 생성"""
    
    PROMPT_TEMPLATE = """
# 입력 데이터

## 1. 학생 기본 정보
- **학생 ID**: {student_id}
- **학생 이름**: {student_name}
- **학년**: {school_grade}학년
- **학기**: {semester}학기
- **수강 과목**: {subjects}

## 2. 학생 인지 유형
**유형**: {cognitive_type}

### 인지 유형별 학습 전략
- **SPEED_FIRST (속도 우선형)**
  - 특징: 빠른 이해력, 반복보다 새로운 문제 선호, 단시간 집중력 우수
  - 학습 전략: 
    * 다양한 유형의 문제를 짧은 세션으로 배치 (25분 학습 + 5분 휴식)
    * 한 문제당 권장 시간: 5-10분
    * 같은 유형 반복 최소화 (최대 2-3문제)
  
- **PRECISION_FIRST (정확도 우선형)**
  - 특징: 꼼꼼한 이해 선호, 반복 학습 효과적, 긴 집중 시간 가능
  - 학습 전략:
    * 같은 유형 문제를 충분히 반복 (4-6문제)
    * 한 문제당 권장 시간: 15-20분
    * 개념 학습 시 50-60분 단위 심화 학습 (50분 학습 + 10분 휴식)
  
- **BURST_STUDY (집중 폭발형)**
  - 특징: 짧은 시간 고강도 집중, 긴 휴식 필요, 몰입 시 극대화
  - 학습 전략:
    * 90분 집중 블록 + 30분 완전 휴식
    * 한 세션에 한 과목만 집중
    * 하루 최대 2-3블록

## 3. 과목별 풀이 습관 분석
{solving_habits}

### 풀이 습관 데이터 활용 가이드

**[풀이 습관 데이터가 있는 경우]**
- 이미지 기반으로 분석된 학생의 실제 풀이 패턴을 깊이 반영하세요.
- `extracted_content`에 명시된 구체적인 습관(예: "수식의 중간 과정 생략", "키워드 마킹 부족")을 과제 설계에 직접 반영
- `detected_tags`를 활용하여 약점 보완 과제 구성 (예: "연산_생략" → "중간 과정 꼭 적기" 지침)

**[풀이 습관 데이터가 없는 경우]**
- 위에 제공된 **인지 유형**과 **과목별 일반 학습 전략**을 최우선 기준으로 사용
- 해당 과목의 표준적인 학습 순서를 따르되, 학생의 페르소나에 맞게 세션 길이와 난이도 조절
- 각 과제에 "왜 이 활동을 하는지" 명확한 학습 목표를 instruction에 포함

**[공통 원칙]**
- 모든 과제는 실행 가능하고 구체적이어야 함
- 학생이 "무엇을, 어떻게, 왜" 공부해야 하는지 명확히 전달
- 인지 유형별 특성(집중 시간, 반복 선호도, 휴식 패턴)을 반드시 준수

## 4. 주간 가용 시간
{weekly_schedule}

# 출력 형식

아래 JSON 형식으로 7일간의 학습 계획을 생성하세요.
**중요**: 반드시 유효한 JSON만 출력하세요. 설명이나 마크다운은 포함하지 마세요.

{{
  "weekly_plan": [
    {{
      "date": "{start_date}",
      "day_of_week": "MONDAY",
      "total_available_minutes": 120,
      "total_planned_minutes": 115,
      "daily_focus": "수학 계산 실수 교정 집중",
      "tasks": [
        {{
          "sequence": 1,
          "category": "수학",
          "title": "이차방정식 단원 전체 문제풀이",
          "assigned_minutes": 25,
          "time_slot": "08:00-08:25",
          "difficulty_level": "중",
          "problem_count": 5,
          "learning_objective": "계산 정확도 향상",
          "instruction": "각 문제마다 풀이 과정을 한 줄도 생략하지 말고 작성하세요.",
          "rest_after": 5
        }}
      ],
      "daily_summary": "오전 시간대 집중력 활용",
      "energy_distribution": "상-상-중-하"
    }}
  ],
  "weekly_summary": {{
    "expected_improvement": "이번 주 계획을 완수하면 수학 계산 정확도 15% 향상 예상",
    "adaptive_notes": "{cognitive_type} 유형에 맞춰 구성된 계획",
    "weekly_goals": ["목표1", "목표2", "목표3"]
  }}
}}

 생성 규칙

## 필수 준수 사항
1. **시간 배분**: 가용 시간의 90-95% 활용, 최소 15분 단위 블록
2. **휴식 시간**: 인지 유형에 맞게 자동 배치
   - SPEED_FIRST: 25분 학습 + 5분 휴식
   - PRECISION_FIRST: 50분 학습 + 10분 휴식
   - BURST_STUDY: 90분 학습 + 30분 휴식
   
3. **난이도 분포**: 상(30%), 중(50%), 하(20%)
   - 오전: 상 난이도 집중
   - 오후: 중 난이도
   - 저녁: 하 난이도 (복습/정리)
   
4. **과목 순환**: 같은 과목 연속 최소화
   - 수학 → 영어 (O)
   - 수학 → 과학 (X, 비슷한 사고방식)
   
5. **에너지 관리**: 
   - 오전(08:00-12:00): 고집중 과제
   - 오후(13:00-17:00): 중집중 과제
   - 저녁(18:00-22:00): 저집중 과제 (암기, 복습)

6. **title 구체화**:
    - tasks 배열의 각 테스크 항목의 제목(title)은 최대한 구체적으로 작성
    - 단원 언급, 페이지 범위 언급 등 최대한 세부 작성

## Instruction 작성 가이드
각 과제의 `instruction` 필드는 다음 형식으로 구체적으로 작성:
- "~하세요" 직접 행동 지시
- 시간/개수 구체적 명시 (예: "10분간", "5문제씩")
- 방법론 제시 (예: "중간 과정을 생략하지 말고", "키워드에 밑줄 치며")

**좋은 예시**:
- "각 문제를 풀기 전 30초간 문제 조건을 다시 읽고, 주어진 값을 모두 적어보세요."
- "지문을 읽으며 핵심 키워드 3개 이상을 형광펜으로 표시하세요."

**나쁜 예시**:
- "문제를 풀어보세요." (너무 추상적)
- "열심히 공부하세요." (행동 불명확)

## 풀이 습관 반영 방식
**데이터 있는 경우**: 
- detected_tags를 직접 과제에 매핑
- 예: "연산_생략" → "계산 과정을 한 줄도 생략하지 말 것" instruction 추가

**데이터 없는 경우**: 
- 해당 과목의 학습 단계별 접근
- 개념 이해(30%) → 문제 적용(50%) → 복습/암기(20%)

## weekly_summary 작성
반드시 다음 3가지 포함:
1. **expected_improvement**: 구체적인 수치나 목표 제시
2. **adaptive_notes**: 학생의 인지 유형/풀이 습관 언급
3. **weekly_goals**: 과목별 구체적 목표 3개

반드시 7일치 계획을 모두 생성하세요.
그리고 꼭 한국어로만 답변하세요.
"""
    
    # 시작 날짜 계산 (다음 월요일)
    start_date = student_data.get('start_date')
    if not start_date:
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        start_date = next_monday.strftime("%Y-%m-%d")
    
    return PROMPT_TEMPLATE.format(
        student_id=student_data['student_id'],
        student_name=student_data.get('student_name', '학생'),
        school_grade=student_data['school_grade'],
        semester=student_data['semester'],
        subjects=', '.join(student_data['subjects']),
        cognitive_type=student_data['cognitive_type'],
        solving_habits=solving_habits,
        weekly_schedule=weekly_schedule,
        start_date=start_date
    )


def calculate_weekly_summary(weekly_plan_data: Dict[str, Any], start_date_str: str) -> Dict[str, Any]:
    """
    주간 계획으로부터 요약 정보 계산
    
    Args:
        weekly_plan_data: AI가 생성한 주간 계획
        start_date_str: 실제 시작 날짜 (YYYY-MM-DD)
    
    Returns:
        {
            'total_study_minutes': int,
            'subject_distribution': dict,
            'focus_areas': list,
            'start_date': str,
            'end_date': str
        }
    """
    weekly_plan = weekly_plan_data.get('weekly_plan', [])
    
    # 총 학습 시간 계산
    total_minutes = sum(
        day['total_planned_minutes'] 
        for day in weekly_plan
    )
    
    # 과목별 시간 분포 계산
    subject_dist = {}
    focus_areas = set()
    
    for day in weekly_plan:
        # 당일 초점 수집
        if day.get('daily_focus'):
            focus_areas.add(day['daily_focus'])
        
        # 과목별 시간 합산
        for task in day.get('tasks', []):
            category = task['category']
            minutes = task['assigned_minutes']
            subject_dist[category] = subject_dist.get(category, 0) + minutes
    
    # ✅ 수정: 파라미터로 받은 start_date 사용
    start_date = start_date_str
    
    # 종료 날짜 계산 (시작일 + 6일)
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=6)
    end_date = end_dt.strftime("%Y-%m-%d")
    
    return {
        'total_study_minutes': total_minutes,
        'subject_distribution': subject_dist,
        'focus_areas': list(focus_areas)[:3],  # 상위 3개
        'start_date': start_date,
        'end_date': end_date
    }
