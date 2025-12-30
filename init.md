### 1️⃣ Request Header

| 항목 | 값 |
| --- | --- |
| Content-Type | `application/json` |
| Authorization | `Bearer {ACCESS_TOKEN}` |

### 2️⃣ Request Param & Body

| 변수명 | 타입 | 설명 | 필수 여부 |
| --- | --- | --- | --- |
| user_id | UUID | 유저 고유 식별자 (users 테이블의 ID) | 필수 |
| school_grade | Integer | 학년 (1, 2, 3) | 필수 |
| semester | Integer | 학기 (1, 2) | 필수 |
| subjects | List<String> | 관심 학습 과목 (예: `["수학","과학"]`) | 필수 |

### 3️⃣ Response Body

| 변수명 | 타입 | 설명 |
| --- | --- | --- |
| success | boolean | 요청 처리 성공 여부 |
| code | int | 상태 코드 (201) |
| message | String | 처리 결과 메시지 |
| data | Object | null | 생성된 프로필 정보 (실패 시 null) |

### 4️⃣ data 상세 (성공 시)

| 변수명 | 타입 | 예시 | 설명 |
| --- | --- | --- | --- |
| profile_id | UUID | `"c0eebc99-..."` | 시스템에서 생성된 프로필 고유 ID |
| user_id | UUID | `"b0eebc99-..."` | 프로필과 연결된 유저 ID |
| streak_days | Integer | `0` | 초기 연속 학습 일수 |
| total_points | Integer | `0` | 초기 랭킹 포인트 |

### ✅ 성공 응답 (201 Created)

```json
{
"success":true,
"code":201,
"message":"기본 정보 등록 완료",
"data":{
"profile_id":"c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
"user_id":"b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
"streak_days":0,
"total_points":0
}
}
```

### ❌ 실패 응답 (400 Bad Request)

```json
{
"success":false,
"code":400,
"message":"해당 유저에 대한 프로필이 이미 존재합니다.",
"data":null
}

```