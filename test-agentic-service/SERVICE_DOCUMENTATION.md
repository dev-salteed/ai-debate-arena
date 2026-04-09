# 오늘 뭐해? 서비스 문서

## 1. 서비스 개요
`오늘 뭐해?`는 사용자가 “오늘 뭐하지?”라고 입력했을 때, 현재 상황에 맞는 활동 추천과 즉시 실행 가능한 일정 초안을 만들어 주는 국내 중심 서비스입니다.

핵심 목표는 아래와 같습니다.
- 검색 피로를 줄인다.
- 여러 플랫폼에 흩어진 후보를 빠르게 좁힌다.
- 추천에서 끝나지 않고 이동 흐름과 링크까지 한 번에 제시한다.

## 2. 사용자 입력 모델
서비스는 아래 입력을 기준으로 동작합니다.
- `user_query`: 자연어 요청
- `region`: 기본 검색 권역
- `companion`: 혼자, 썸, 연인, 친구, 가족, 상관없음
- `weather`: 맑음, 비, 흐림, 눈, 상관없음
- `time_slot`: 오전, 오후, 저녁, 하루 종일, 상관없음
- `budget_level`: 가볍게, 보통, 여유, 상관없음
- `mobility`: 도보 위주, 대중교통, 택시 가능, 상관없음

## 3. 에이전트 구조
### ContextAnalyzer
- 자연어에서 지역, 동행, 날씨, 시간대, 예산감, 이동 방식, 키워드를 추출합니다.
- `parsed_context`를 채우고 후속 검색의 기준을 만듭니다.

### Retriever
- 상황 요약형, 카테고리 탐색형, 운영/예약 확인형 쿼리를 여러 개 생성합니다.
- DuckDuckGo 검색을 수행하고 결과를 점수화 가능한 형태로 저장합니다.
- 후보가 빈약하면 한 번 더 넓은 검색으로 재시도합니다.

### Curator
- 검색 결과를 URL 기준으로 중복 제거합니다.
- 광고성 결과를 낮게 평가하고 카테고리/지역/예약 가능성 신호를 반영합니다.
- 3~5개의 추천 카드로 정리합니다.

### Planner
- 추천 카드를 시간대별 타임라인으로 변환합니다.
- 같은 권역 안에서 이어지는 동선을 문장으로 요약합니다.
- 예약 링크 묶음과 실행 팁을 포함한 `final_plan`을 구성합니다.

### ResponseComposer
- `final_plan`의 필수 키를 보정합니다.
- 추천 개수나 링크가 부족할 경우 fallback 데이터를 채워 UI/API가 바로 사용할 수 있게 마무리합니다.

## 4. 검색 전략
- 기본 `RAG_MODE`는 `web`입니다.
- DuckDuckGo 결과를 멀티쿼리로 수집합니다.
- 후처리 단계에서 다음을 수행합니다.
  - URL canonicalization
  - 중복 제거
  - 광고성 키워드 필터
  - 카테고리 추론
  - 예약 링크 추출
  - 상황 키워드 매칭 기반 점수화

선택적으로 `vector` 또는 `hybrid` 모드를 둘 수 있지만, 현재 MVP는 웹 검색 중심 사용을 전제로 합니다.

## 5. 상태 구조
그래프 상태는 `TodayWhatState` 하나로 통일합니다.
- `user_query`
- `region`
- `companion`
- `weather`
- `time_slot`
- `budget_level`
- `mobility`
- `parsed_context`
- `search_queries`
- `raw_search_results`
- `curated_candidates`
- `final_plan`
- `decision_memory`
- `constraints_memory`
- `messages`
- `current_step`
- `completed`

## 6. UI 구조
Streamlit UI는 다음 구역으로 구성됩니다.
- 상단 히어로: 서비스 설명과 대표 문구
- 입력 패널: 자연어 요청과 상황 선택 칩
- 사이드바: 이어하기, RAG 토글, 로그, 최근 메모리
- 결과 영역: 요약 카드, 추천 카드, 타임라인, 링크 패널, 원본 결과 확인

## 7. API 계약
### Health
- `GET /api/health`
- 응답: `{"status": "ok"}`

### Plan
- `POST /api/plan`
- 요청 본문은 사용자 입력 모델과 동일합니다.
- 응답은 전체 state를 포함하며, 실제 화면/API 소비는 `final_plan`을 중심으로 사용합니다.

## 8. 검증 현황
로컬 가상환경 기준 아래 검증을 수행했습니다.
- `./venv/bin/python -m py_compile app/main.py app/api/main.py app/retrieval/*.py app/workflow/agents/*.py app/workflow/*.py`
- `./venv/bin/python -m unittest discover -s tests -v`
- `./venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8001`
- `./venv/bin/streamlit run app/main.py --server.headless true --server.port 8502`

## 9. 한계와 다음 확장 포인트
- 지도 API를 붙이지 않았기 때문에 동선은 권역 중심 텍스트 요약 수준입니다.
- 날씨는 외부 API 없이 사용자 입력/자연어에서만 반영합니다.
- 예약 링크는 DuckDuckGo 검색 결과에 노출된 URL만 사용합니다.
- 향후 확장 시 후보 저장, 사용자 선호 학습, 지도 기반 ETA 계산을 붙일 수 있습니다.
