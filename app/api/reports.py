"""
일간 리포트 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime, timedelta
from typing import Optional
import logging
import uuid

from ..schemas import (
    DailyReportCreateRequest,
    DailyReportData,
    APIResponse,
    HistoryAPIResponse,
    ReportHistoryData,
    PaginatedReportsResponse,
    PaginatedReportsData
)
from ..services.report_service import ReportGenerationService
from ..models import DailyReport
from ..database import get_db
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports/daily", tags=["reports"])

# ReportGenerationService 싱글톤 인스턴스
report_service = ReportGenerationService()


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_report(
    request: DailyReportCreateRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일간 리포트 생성

    - **user_id**: 유저 고유 식별자 (UUID)
    - **report_date**: 리포트 날짜 (선택, 기본값: 오늘)
    - **total_study_time**: 총 학습 시간 (분)
    - **achievement_rate**: 평균 성취도 (0-100)
    - **question_count**: 총 질문 횟수
    - **most_immersive_subject**: 가장 몰입한 과목
    - **subject_details**: 과목별 상세 정보 리스트

    Returns:
        201: 리포트 생성 성공
        200: 기존 리포트 반환 (중복 방지)
        400: 입력 데이터 검증 실패
        401: 인증 실패
        500: 서버 내부 오류
    """
    try:
        logger.info(f"리포트 생성 요청: user_id={request.user_id}, date={request.report_date}")

        # 1. 기존 리포트 확인 (중복 방지)
        if request.report_date:
            target_date = date.fromisoformat(request.report_date)
        else:
            target_date = datetime.now().date()

        result = await db.execute(
            select(DailyReport).filter(
                DailyReport.user_id == request.user_id,
                DailyReport.report_date == target_date
            )
        )
        existing_report = result.scalars().first()

        if existing_report:
            logger.info(f"기존 리포트 반환: {existing_report.report_id}")
            return APIResponse(
                success=True,
                code=200,
                message="해당 날짜의 리포트가 이미 존재합니다",
                data=DailyReportData(**existing_report.to_dict())
            )

        # 2. AI 리포트 생성
        try:
            ai_content = await report_service.generate_report(
                total_study_time=request.total_study_time,
                achievement_rate=request.achievement_rate,
                question_count=request.question_count,
                most_immersive_subject=request.most_immersive_subject,
                subject_details=[s.model_dump() for s in request.subject_details]
            )
        except Exception as e:
            logger.error(f"AI 리포트 생성 실패: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI 리포트 생성 중 오류가 발생했습니다"
            )

        # 3. 데이터베이스 저장
        new_report = DailyReport(
            report_id=uuid.uuid4(),
            user_id=request.user_id,
            report_date=target_date,
            total_study_time=request.total_study_time,
            achievement_rate=request.achievement_rate,
            question_count=request.question_count,
            most_immersive_subject=request.most_immersive_subject,
            subject_details=[s.model_dump() for s in request.subject_details],
            ai_summary_title=ai_content["ai_summary_title"],
            ai_good_point=ai_content["ai_good_point"],
            ai_improvement_point=ai_content["ai_improvement_point"],
            keywords=ai_content["keywords"],
            passion_temp=ai_content["passion_temp"],
            subject_badges=ai_content["subject_badges"]
        )

        try:
            db.add(new_report)
            await db.commit()
            await db.refresh(new_report)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"데이터베이스 무결성 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="해당 날짜의 리포트가 이미 존재합니다"
            )

        logger.info(f"리포트 생성 완료: {new_report.report_id}")

        return APIResponse(
            success=True,
            code=201,
            message="일간 리포트 생성 완료",
            data=DailyReportData(**new_report.to_dict())
        )

    except HTTPException:
        raise

    except ValueError as e:
        logger.error(f"입력 데이터 검증 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"입력 데이터 유효성 검증 실패: {str(e)}"
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"리포트 생성 중 예상치 못한 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리포트 생성 중 오류가 발생했습니다"
        )


@router.get("", response_model=PaginatedReportsResponse)
async def get_all_reports(
    page: int = 1,
    page_size: int = 20,
    user_id: Optional[uuid.UUID] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    모든 일간 리포트를 페이지네이션과 필터링을 통해 조회

    Query Parameters:
        page: 페이지 번호 (1부터 시작, 기본값: 1)
        page_size: 페이지당 항목 수 (기본값: 20, 최대: 100)
        user_id: 특정 사용자 필터링 (선택)
        start_date: 시작 날짜 (YYYY-MM-DD, 선택)
        end_date: 종료 날짜 (YYYY-MM-DD, 선택)

    Returns:
        200: 조회 성공 (빈 결과 포함)
        400: 잘못된 파라미터
        401: 인증 실패
    """
    try:
        # 파라미터 검증
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페이지 번호는 1 이상이어야 합니다"
            )

        if page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페이지 크기는 1-100 사이여야 합니다"
            )

        # 기본 쿼리 구성
        query = select(DailyReport)
        filters = []

        # 필터 적용
        if user_id:
            filters.append(DailyReport.user_id == user_id)

        if start_date:
            try:
                start = datetime.fromisoformat(start_date).date()
                filters.append(DailyReport.report_date >= start)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date 형식이 올바르지 않습니다 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end = datetime.fromisoformat(end_date).date()
                filters.append(DailyReport.report_date <= end)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date 형식이 올바르지 않습니다 (YYYY-MM-DD)"
                )

        # 필터 적용
        if filters:
            query = query.filter(and_(*filters))

        # 전체 개수 조회
        count_query = select(func.count()).select_from(DailyReport)
        if filters:
            count_query = count_query.filter(and_(*filters))

        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

        # 페이지네이션 적용
        offset = (page - 1) * page_size
        query = query.order_by(DailyReport.report_date.desc()).offset(offset).limit(page_size)

        # 데이터 조회
        result = await db.execute(query)
        reports = result.scalars().all()

        # 응답 데이터 구성
        report_list = [DailyReportData(**r.to_dict()) for r in reports]

        # 전체 페이지 수 계산
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

        logger.info(f"리포트 목록 조회: page={page}, total_count={total_count}")

        return PaginatedReportsResponse(
            success=True,
            code=200,
            message="리포트 목록 조회 성공",
            data=PaginatedReportsData(
                reports=report_list,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"리포트 목록 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리포트 목록 조회 중 오류가 발생했습니다"
        )


@router.get("/{user_id}", response_model=APIResponse)
async def get_daily_report(
    user_id: uuid.UUID,
    date: Optional[str] = None,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 날짜의 일간 리포트 조회

    Args:
        user_id: 사용자 UUID
        date: 조회할 날짜 (YYYY-MM-DD, 선택, 기본값: 오늘)

    Returns:
        200: 조회 성공
        404: 리포트 없음
        401: 인증 실패
    """
    try:
        # 날짜 파라미터 처리
        if date is None:
            target_date = datetime.now().date()
        else:
            target_date = datetime.fromisoformat(date).date()

        logger.info(f"리포트 조회: user_id={user_id}, date={target_date}")

        # 데이터베이스 조회
        result = await db.execute(
            select(DailyReport).filter(
                DailyReport.user_id == user_id,
                DailyReport.report_date == target_date
            )
        )
        report = result.scalars().first()

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{target_date} 날짜의 리포트를 찾을 수 없습니다"
            )

        return APIResponse(
            success=True,
            code=200,
            message="리포트 조회 성공",
            data=DailyReportData(**report.to_dict())
        )

    except HTTPException:
        raise

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"
        )

    except Exception as e:
        logger.error(f"리포트 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리포트 조회 중 오류가 발생했습니다"
        )


@router.get("/{user_id}/history", response_model=HistoryAPIResponse)
async def get_report_history(
    user_id: uuid.UUID,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일간 리포트 히스토리 조회

    Args:
        user_id: 사용자 UUID
        start_date: 시작 날짜 (선택, 기본값: 30일 전)
        end_date: 종료 날짜 (선택, 기본값: 오늘)
        limit: 최대 조회 개수 (기본값: 30)

    Returns:
        200: 조회 성공 (통계 포함)
        401: 인증 실패
    """
    try:
        # 기본 날짜 설정
        if end_date is None:
            end = datetime.now().date()
        else:
            end = datetime.fromisoformat(end_date).date()

        if start_date is None:
            start = end - timedelta(days=30)
        else:
            start = datetime.fromisoformat(start_date).date()

        logger.info(f"리포트 히스토리 조회: user_id={user_id}, {start} ~ {end}")

        # 데이터베이스 조회
        result = await db.execute(
            select(DailyReport)
            .filter(
                DailyReport.user_id == user_id,
                DailyReport.report_date >= start,
                DailyReport.report_date <= end
            )
            .order_by(DailyReport.report_date.desc())
            .limit(limit)
        )
        reports = result.scalars().all()

        # 응답 데이터 구성
        report_list = [DailyReportData(**r.to_dict()) for r in reports]

        # 통계 계산
        if reports:
            avg_passion = sum(r.passion_temp for r in reports if r.passion_temp) / len(reports)
            avg_study_time = sum(r.total_study_time for r in reports) / len(reports)
            avg_achievement = sum(r.achievement_rate for r in reports) / len(reports)
        else:
            avg_passion = avg_study_time = avg_achievement = 0

        return HistoryAPIResponse(
            success=True,
            code=200,
            message="리포트 히스토리 조회 성공",
            data=ReportHistoryData(
                reports=report_list,
                total_count=len(reports),
                date_range={
                    "start": start.isoformat(),
                    "end": end.isoformat()
                },
                statistics={
                    "avg_passion_temp": round(avg_passion, 1),
                    "avg_study_time": round(avg_study_time, 1),
                    "avg_achievement_rate": round(avg_achievement, 1)
                }
            )
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"
        )

    except Exception as e:
        logger.error(f"히스토리 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="히스토리 조회 중 오류가 발생했습니다"
        )


@router.delete("/{user_id}/{report_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_report(
    user_id: uuid.UUID,
    report_date: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    일간 리포트 삭제

    Args:
        user_id: 사용자 UUID
        report_date: 삭제할 리포트 날짜 (YYYY-MM-DD)

    Returns:
        204: 삭제 성공
        404: 리포트 없음
        401: 인증 실패
    """
    try:
        target_date = datetime.fromisoformat(report_date).date()

        result = await db.execute(
            select(DailyReport).filter(
                DailyReport.user_id == user_id,
                DailyReport.report_date == target_date
            )
        )
        report = result.scalars().first()

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="삭제할 리포트를 찾을 수 없습니다"
            )

        await db.delete(report)
        await db.commit()

        logger.info(f"리포트 삭제 완료: user_id={user_id}, date={report_date}")

    except HTTPException:
        raise

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"리포트 삭제 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리포트 삭제 중 오류가 발생했습니다"
        )
