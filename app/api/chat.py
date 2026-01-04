"""
AI 튜터 채팅 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
from datetime import datetime
import uuid

from ..database import get_db
from ..models import StudentProfile, ChatMessage, ProblemAnalysisLog, User
from ..schemas import (
    ChatRequest,
    ChatResponse,
    ChatResponseData,
    ChatHistoryResponse,
    ChatHistoryData,
    ChatHistoryItem
)
from ..dependencies import get_current_user
from ..services.ai_tutor import generate_tutor_response, get_fallback_response

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)


@router.post(
    "",
    response_model=ChatResponse,
    summary="AI 튜터와 채팅",
    description="AI 튜터에게 질문하고 답변을 받습니다. 대화 내용은 자동으로 저장됩니다."
)
async def chat_with_tutor(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI 튜터와 채팅
    
    - **message**: 학생의 질문
    - **problem_log_id**: 특정 문제 관련 질문인 경우 (선택)
    """
    
    try:
        # 1. 메시지 검증
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="메시지 내용을 입력해주세요"
            )
        
        # 2. 학생 프로필 조회
        profile_result = await db.execute(
            select(StudentProfile).filter(StudentProfile.user_id == current_user_id)
        )
        profile = profile_result.scalars().first()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="학생 프로필을 찾을 수 없습니다"
            )
        
        # 3. 유저 정보 조회 (이름 가져오기)
        user_result = await db.execute(
            select(User).filter(User.id == current_user_id)
        )
        user = user_result.scalars().first()
        
        # 4. 학생 컨텍스트 준비
        student_context = {
            'student_name': user.name if user else '학생',
            'school_grade': profile.school_grade,
            'semester': profile.semester,
            'cognitive_type': profile.cognitive_type.value if profile.cognitive_type else None,
            'subjects': profile.subjects
        }
        
        # 5. 문제 컨텍스트 조회 (있는 경우)
        problem_context = None
        if request.problem_log_id:
            problem_result = await db.execute(
                select(ProblemAnalysisLog).filter(
                    ProblemAnalysisLog.id == request.problem_log_id
                )
            )
            problem = problem_result.scalars().first()
            
            if problem:
                problem_context = {
                    'subject': problem.subject,
                    'extracted_text': problem.extracted_text,
                    'detected_concepts': problem.detected_concepts or [],
                    'difficulty_level': problem.difficulty_level
                }
        
        # 6. 최근 대화 내역 조회 (컨텍스트용)
        history_result = await db.execute(
            select(ChatMessage)
            .filter(ChatMessage.student_id == profile.id)
            .order_by(desc(ChatMessage.created_at))
            .limit(10)
        )
        recent_messages = history_result.scalars().all()
        
        chat_history = [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in reversed(recent_messages)  # 시간순 정렬
        ]
        
        # 7. AI 응답 생성
        try:
            ai_response = await generate_tutor_response(
                user_message=request.message,
                student_context=student_context,
                problem_context=problem_context,
                chat_history=chat_history
            )
        except Exception as e:
            print(f"AI 응답 생성 실패: {str(e)}")
            # 폴백 응답 사용
            ai_response = get_fallback_response()
        
        # 8. 사용자 메시지 저장
        user_msg = ChatMessage(
            id=uuid.uuid4(),
            student_id=profile.id,
            problem_log_id=request.problem_log_id,
            role="user",
            content=request.message,
            student_sentiment=None,
            created_at=datetime.utcnow()
        )
        db.add(user_msg)
        await db.flush()
        
        # 9. AI 응답 메시지 저장
        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            student_id=profile.id,
            problem_log_id=request.problem_log_id,
            role="assistant",
            content=ai_response["assistant_message"],
            student_sentiment=ai_response["student_sentiment"].get("learning_signal"),  # 간단한 요약만 저장
            created_at=datetime.utcnow()
        )
        db.add(assistant_msg)
        await db.flush()
        
        # 10. 커밋
        await db.commit()
        
        # 11. 응답 데이터 생성
        from ..schemas import StudentSentimentAnalysis
        
        response_data = ChatResponseData(
            user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id,
            user_message=request.message,
            assistant_message=ai_response["assistant_message"],
            student_sentiment=StudentSentimentAnalysis(**ai_response["student_sentiment"]),
            created_at=assistant_msg.created_at.isoformat() + "Z"
        )
        
        return ChatResponse.success_res(
            data=response_data,
            message="채팅 처리 성공"
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류가 발생했습니다: {str(e)}"
        )


# @router.get(
#     "/history",
#     response_model=ChatHistoryResponse,
#     summary="채팅 히스토리 조회",
#     description="학생의 채팅 히스토리를 조회합니다."
# )
# async def get_chat_history(
#     limit: int = Query(50, description="조회할 메시지 개수", ge=1, le=100),
#     problem_log_id: Optional[str] = Query(None, description="특정 문제 관련 대화만 조회"),
#     current_user_id: str = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     채팅 히스토리 조회
    
#     - **limit**: 조회할 메시지 개수 (기본 50개, 최대 100개)
#     - **problem_log_id**: 특정 문제 관련 대화만 조회 (선택)
#     """
    
#     try:
#         # 1. 학생 프로필 조회
#         profile_result = await db.execute(
#             select(StudentProfile).filter(StudentProfile.user_id == current_user_id)
#         )
#         profile = profile_result.scalars().first()
        
#         if not profile:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="학생 프로필을 찾을 수 없습니다"
#             )
        
#         # 2. 쿼리 구성
#         query = select(ChatMessage).filter(ChatMessage.student_id == profile.id)
        
#         if problem_log_id:
#             query = query.filter(ChatMessage.problem_log_id == problem_log_id)
        
#         query = query.order_by(desc(ChatMessage.created_at)).limit(limit)
        
#         # 3. 메시지 조회
#         messages_result = await db.execute(query)
#         messages = messages_result.scalars().all()
        
#         # 4. 응답 데이터 생성
#         message_items = [
#             ChatHistoryItem(
#                 message_id=msg.id,
#                 role=msg.role,
#                 content=msg.content,
#                 student_sentiment=msg.student_sentiment,
#                 created_at=msg.created_at.isoformat() + "Z",
#                 problem_log_id=msg.problem_log_id
#             )
#             for msg in reversed(messages)  # 시간순 정렬
#         ]
        
#         response_data = ChatHistoryData(
#             total_count=len(message_items),
#             messages=message_items
#         )
        
#         return ChatHistoryResponse.success_res(
#             data=response_data,
#             message="채팅 히스토리 조회 성공"
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"서버 오류가 발생했습니다: {str(e)}"
#         )