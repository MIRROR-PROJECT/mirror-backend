import base64
import requests
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict
import os

router = APIRouter(prefix="/api/payment")

# 결제 승인 요청 데이터 모델
class PaymentConfirmRequest(BaseModel):
    paymentKey: str
    orderId: str
    amount: int

@router.post("/confirm")
async def confirm_payment(data: PaymentConfirmRequest):
    # 1. 시크릿 키 로드 및 인증 헤더 생성
    secret_key = os.getenv("TOSS_SECRET_KEY")
    # 토스 API는 키 뒤에 콜론(:)을 붙여 Base64로 인코딩한 값을 요구함
    auth_token = base64.b64encode(f"{secret_key}:".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_token}",
        "Content-Type": "application/json"
    }

    # 2. 토스 승인 API 호출 (POST 요청)
    url = "https://api.tosspayments.com/v1/payments/confirm"
    response = requests.post(url, json=data.dict(), headers=headers)
    res_json = response.json()

    # 3. 승인 결과 처리
    if response.status_code == 200:
        # [성공] 여기서 실제 돈이 빠져나감
        # TODO: DB를 업데이트하여 유저에게 AI 튜터 이용권 지급
        # update_user_subscription(data.orderId)
        return {"status": "success", "detail": "결제가 성공적으로 완료되었습니다."}
    else:
        # [실패] 결제 취소 사유 등을 응답
        raise HTTPException(status_code=response.status_code, detail=res_json)