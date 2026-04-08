# 오늘 뭐먹지 상세 문서

## 1. 서비스 개요

### 1.1 해결하려는 문제

- 광고와 SEO 중심 검색 결과 때문에 사용자가 직접 블로그와 후기를 훑어야 하는 부담이 큽니다.
- `데이트`, `혼밥`, `작업`, `회식` 같은 상황 조건은 일반 검색만으로 반영하기 어렵습니다.
- 최신성은 필요하지만 정보량은 과도해서, 의사결정에 바로 쓸 수 있는 정제 결과가 부족합니다.

### 1.2 가치 제안

- 자연어 한 줄만으로 지역, 분위기, 목적, 가격대를 해석합니다.
- 로컬 지식과 웹 검색을 결합해 최신성 있는 추천 근거를 수집합니다.
- 후보를 근거 중심으로 압축하고, 최종 추천을 구조화된 포맷으로 제시합니다.
- 이어서 재실행 시 이전 제약과 의사결정 메모리를 이어받아 점진적으로 추천을 좁힙니다.

## 2. 시스템 설계

### 2.1 Prompt Engineering

- 역할 기반 프롬프트
  - Query Parser, Place Search, RAG Processor, Recommendation Agent 각각에 전용 역할을 부여했습니다.
- Few-shot 예시
  - 모든 핵심 에이전트 프롬프트에 예시 입력/출력 JSON을 포함했습니다.
- Structured Output
  - 각 단계는 JSON 스키마를 강제합니다.
- 응답 가드
  - `response_guard.py`가 코드블록 제거와 JSON 파싱을 담당합니다.
  - 필수 키가 누락되면 1회 자동 리페어를 시도합니다.

### 2.2 LangGraph Agent Flow

```text
START
  -> SUPERVISOR
  -> QUERY_PARSER
  -> SUPERVISOR
  -> PLACE_SEARCH
  -> SUPERVISOR
  -> RAG_PROCESSOR
  -> SUPERVISOR
  -> RECOMMENDATION
  -> END
```

Supervisor 동작:

- 기본적으로 순차 실행을 유지합니다.
- `RAG_PROCESSOR` 이후 후보가 충분하지 않으면 `PLACE_SEARCH`로 한 번 더 보내 검색 범위를 완화합니다.
- 이때 `constraints_memory["broaden_search"] = "true"`를 남겨 다음 프롬프트에서 활용합니다.

### 2.3 RAG 구성

- 로컬 데이터
  - `app/retrieval/data/dining_knowledge.json`
  - 조용한 카페, 데이트 식당, 혼밥, 회식, 검색 확장 전략 등 추천 힌트를 담았습니다.
- 벡터 검색
  - `FAISS` 기반 로컬 유사도 검색
- 웹 검색
  - `DuckDuckGo Search`
- 하이브리드 정책
  - 먼저 벡터 검색을 수행합니다.
  - 결과가 부족하면 웹 검색을 보조로 사용합니다.

## 3. 상태 모델

핵심 상태 필드:

- `user_query`
- `parsed_query`
- `search_brief`
- `candidate_places`
- `recommendations`
- `search_iterations`
- `max_search_iterations`
- `decision_memory`
- `constraints_memory`
- `current_step`
- `messages`
- `completed`

UI 보조 필드:

- `thread_id`
- `continued_last_run`

## 4. UI 구성

`app/main.py`는 Streamlit 기반으로 다음 UX를 제공합니다.

- 자연어 입력 중심 폼
- 예시 프롬프트 빠른 입력
- RAG on/off 스위치
- 이어서 재실행 옵션
- 커스텀 CSS 기반 따뜻한 다이닝 가이드 스타일
- 파싱 결과, 검색 브리프, 후보 카드, 최종 추천, 후속 질문, 메모리 시각화

## 5. API

### 5.1 엔드포인트

- `GET /api/health`
- `POST /api/recommend`

### 5.2 요청 스키마

```json
{
  "user_query": "강남에서 조용한 카페 추천해줘",
  "enable_rag": true,
  "max_search_iterations": 2
}
```

### 5.3 응답 특징

- `result`는 LangGraph 최종 상태 전체를 반환합니다.
- UI 없이도 구조화 추천 결과를 바로 소비할 수 있습니다.

## 6. 테스트 전략

테스트 범위:

- API 응답과 validation
- LangGraph 체크포인터/스토어 재사용
- 프롬프트 구성과 JSON 리페어
- Search Agent의 tool 연결
- Search Service의 hybrid fallback
- Supervisor 재검색 라우팅
- UI 멀티턴 상태 생성
- Tool runner의 ReAct 루프

실행 명령:

```bash
source venv/bin/activate
python -m unittest discover -s tests
```

## 7. 변경 포인트 요약

이번 개편에서 제거한 흔적:

- 이전 추천 도메인에 묶여 있던 주제별 워크플로우
- 이전 데이터셋 및 FAISS 인덱스 파일명
- 이전 서비스 기준 테스트 파일과 설명 문서
- 이전 에이전트 파일명과 역할 구분

이번 개편에서 추가한 것:

- 음식점/카페 추천용 멀티에이전트 그래프
- 맛집/카페 추천 도메인 데이터셋
- 카드형 추천 UI
- `/api/recommend` 엔드포인트
- 설치 가능하도록 정리한 `requirements.txt`
