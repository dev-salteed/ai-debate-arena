# 오늘 뭐해?

`오늘 뭐해?`는 사용자의 자연어 요청을 바탕으로 상황을 해석하고, DuckDuckGo 검색 결과를 정제해 3~5개의 활동 추천과 바로 실행 가능한 동선형 일정을 만들어주는 에이전틱 서비스입니다.

## 핵심 경험
- 한 줄 입력으로 `지역 + 동행 + 날씨 + 시간대 + 예산 + 이동 방식`을 함께 해석합니다.
- DuckDuckGo 기반 멀티쿼리 검색으로 전시, 카페, 체험, 산책, 공연, 맛집 후보를 수집합니다.
- 광고성/중복 링크를 줄이고 예약 가능성까지 고려해 추천 카드를 3~5개로 정리합니다.
- 추천 결과를 타임라인, 권역 중심 동선, 예약 링크 묶음으로 재구성합니다.
- Streamlit UI와 FastAPI API 모두 같은 LangGraph 워크플로우를 사용합니다.

## 워크플로우
```text
User Input
 -> ContextAnalyzer
 -> Retriever
 -> Curator
 -> Planner
 -> ResponseComposer
 -> UI / API
```

## 응답 구조
최종 `final_plan`은 아래 키를 항상 포함합니다.

- `summary`
- `situation_tags`
- `recommendations`
- `timeline`
- `route_summary`
- `booking_links`
- `notes`
- `follow_up_prompt`
- `fallback_option`
- `quick_tips`

각 추천 항목은 아래 필드를 가집니다.

- `name`
- `category`
- `area`
- `why_fit`
- `indoor_outdoor`
- `estimated_cost`
- `best_for`
- `source_url`
- `reservation_url`

## 기술 구성
- LangGraph: 상태 그래프와 멀티스텝 라우팅
- LangChain Core / OpenAI: 선택적 LLM 및 tool-call 기반 확장 지점
- DuckDuckGo Search: 실시간 검색 수집
- Streamlit: 탐색형 UI
- FastAPI: API 엔드포인트
- FAISS: 선택적 로컬 지식 검색 유틸

## API
### `GET /api/health`
```json
{"status": "ok"}
```

### `POST /api/plan`
요청 예시:
```json
{
  "user_query": "비 오는 날 성수에서 데이트 뭐해?",
  "region": "성수",
  "companion": "썸",
  "weather": "비",
  "time_slot": "저녁",
  "budget_level": "보통",
  "mobility": "대중교통",
  "enable_rag": true,
  "thread_id": null
}
```

## 실행 방법
루트 `.env`에 Azure OpenAI 관련 환경 변수를 준비합니다.

```bash
AOAI_API_KEY=...
AOAI_ENDPOINT=...
AOAI_DEPLOY_GPT4O=...
AOAI_API_VERSION=...
AOAI_EMBEDDING_DEPLOYMENT=...
```

앱 실행:
```bash
cd test-agentic-service
chmod +x run.sh
./run.sh
```

API 실행:
```bash
cd test-agentic-service
./venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

## 테스트
```bash
cd test-agentic-service
./venv/bin/python -m unittest discover -s tests -v
```

현재 기준 회귀 테스트는 23개이며 모두 통과합니다.
