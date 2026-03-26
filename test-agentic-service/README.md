# 저기어때 - 여행 계획 에이전틱 서비스

## 개요

**저기어때**는 사용자의 여행 주제만 입력하면 AI 에이전트들이 협력하여 완벽한 여행 계획을 자동으로 생성해주는 MVP 서비스입니다.

## 4.2 필수 기술 요소 구현 현황

| 항목 | 구현 상태 | 구현 내용 | 미구현/보강 필요 |
|------|----------|-----------|------------------|
| Prompt Engineering | 상당 구현 | 역할 기반 system prompt, 입력 구조화, JSON 출력 강제, Few-shot 예시, 필수 키 누락 시 JSON 보정 1회 | CoT/추론 단계의 정교한 표준화 |
| LangChain/LangGraph Agent | 구현됨 | Multi-Agent(Supervisor+3 Worker), Tool Calling(`bind_tools`), 공통 ReAct policy, 상태 메모리 누적, 항공권 실패 신호 기반 1회 재추천 루프 | Worker 간 완전 자율 협업(A2A)까지는 미적용 |
| RAG | 상당 구현 | FAISS+웹 하이브리드, `search_city_context`, `search_flight_context`, Flight tool observation 기반 통합 | 재랭킹/멀티소스 결합 고도화 |
| 맥락 유지/멀티턴 | 부분 구현 | LangGraph `MemorySaver` + `InMemoryStore`, Streamlit thread_id 기반 연속 실행 | 프로세스 재시작 시 맥락 소실(메모리형 한계), API 멀티턴 미반영 |
| 서비스 개발/패키징 | 구현됨 | Streamlit UI, FastAPI 백엔드(`GET /api/health`, `POST /api/plan`) | - |

### 근거 코드 위치
- Prompt/Agent: `app/workflow/agents/*`
- LangGraph 분기: `app/workflow/graph.py`, `app/workflow/agents/supervisor_agent.py`
- Tool Calling: `app/workflow/agents/tool_runner.py`
- 멀티턴(UI): `app/main.py` (`thread_id`, continue run)
- RAG(FAISS/하이브리드): `app/retrieval/vector_store.py`, `app/retrieval/search_service.py`, `app/retrieval/knowledge_loader.py`

### 미구현 체크리스트 (우선순위)
- [x] P1 Prompt: Few-shot + 일관성 보정 템플릿
- [x] P1 Memory: 상태 메모리 누적/재사용 고도화
- [x] P1 FastAPI 백엔드: `GET /api/health`, `POST /api/plan`
- [x] P2 ReAct: Tool 실행 흐름 포맷 표준화
- [x] P2 LangGraph Checkpointer/Store: 메모리형 최소 구현 + UI 멀티턴 연동

## 피드백 반영 체크포인트

1. 과제 개요 문서 충실도
   - 기술별 설명(Prompt/LangGraph/RAG/UI)과 구현 근거 파일을 본 문서와 상세 문서에 동시 반영
   - 과거 문구 중 현재 구현과 불일치하는 표현(예: Tool Calling 미적용)을 삭제/정정
   - 1단계 원문 기준 오해 소지가 있던 "Tool Calling 미적용" 서술을 현재 구현(`tool_runner`, `bind_tools`) 기준으로 정합화
2. 검색 지식 통합
   - 도시 추천: `search_city_context` tool 기반
   - 항공권: `search_flight_context` tool observation을 `search_context`로 받아 응답/가용성 판단에 반영
3. Multi-Agent 구조 설명 정밀화
   - 역할 분리는 유지하되, 현재 구조는 Supervisor 중심 순차 협업임을 명시
   - 항공권 실패 시 `needs_replan/replan_reason`로 City 재추천을 요청하는 1회 협업 루프 반영
4. 맥락 유지/멀티턴
   - LangGraph `MemorySaver` + `InMemoryStore` 적용
   - Streamlit UI에서 동일 `thread_id`로 이어서 재실행 지원
   - 한계: 메모리형 저장소라 프로세스 재시작 시 맥락 유지 불가

## 주요 기능

1. **여행 도시 추천** (Agent A)
   - 여행 주제에 맞는 해외 도시 2~3개 추천
   - 각 도시별 추천 이유 제공
   - **RAG**: DuckDuckGo 웹 검색으로 실시간 여행지 정보 수집

2. **항공권 검색** (Agent B)
   - 왕복 항공권 정보 제공
   - 자동 날짜 계산 (출발일: 오늘+30일)
   - **RAG**: 웹 검색으로 실제 항공권 가격 참고

3. **여행 일정 + 예산 계획** (Agent C)
   - Day별 상세 일정 생성
   - 항공권/숙소/식비/기타 예산 분배
   - **RAG**: 웹 검색으로 현지 명소, 맛집 정보 수집

4. **로깅 시스템**
   - 모든 에이전트의 입출력 로깅
   - RAG 검색 쿼리 및 결과 로깅
   - UI에서 실시간 로그 확인 가능

## 기술 스택

- **LangGraph**: 에이전트 워크플로우 관리
- **LangChain**: LLM 인터페이스
- **Streamlit**: 웹 UI
- **OpenAI GPT**: 자연어 처리
- **DuckDuckGo Search**: RAG 웹 검색
- **Python Logging**: 입출력 로깅

## 에이전트 구조

```
입력 (여행 주제)
    ↓
[Agent A: 도시 추천]
    ↓
[Agent B: 항공권 검색]
    ↓
[Agent C: 일정+예산]
    ↓
출력 (완성된 여행 계획)
```

### 에이전트 역할

- **CityRecommenderAgent**: 여행 주제에 맞는 도시 추천
- **FlightSearchAgent**: 항공권 정보 검색
- **ItineraryAgent**: 일정 및 예산 계획
- **SupervisorAgent**: 전체 워크플로우 제어 (현재는 순차 실행)

## 설치 및 실행

### 1. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 설정하세요:

```bash
OPENAI_API_KEY=your_api_key_here
```

### 2. 실행

```bash
chmod +x run.sh
./run.sh
```

또는 수동 실행:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
```

### 2-1. FastAPI 백엔드 실행

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

주요 엔드포인트:
- `GET /api/health`
- `POST /api/plan`

### 3. 벡터DB 인덱스 빌드 (권장)

하이브리드 RAG는 로컬 FAISS 인덱스가 있을 때 벡터 검색을 우선 사용합니다.

```bash
python -m app.retrieval.build_index --reset
```

인덱스가 없거나 로드에 실패하면 자동으로 웹 검색(DuckDuckGo) fallback이 동작합니다.

### 4. 그래프 시각화

```bash
python app/workflow/graph.py
```

## 사용 방법

1. 브라우저에서 `http://localhost:8501` 접속
2. 왼쪽 사이드바에서 여행 정보 입력:
   - 여행 주제 (필수)
   - 여행 일수
   - 예산 (선택)
   - 출발 도시
   - **RAG 활성화** 체크박스 (기본: ON)
3. "여행 계획 시작" 버튼 클릭
4. 결과 확인:
   - 추천 도시 탭
   - 항공권 탭
   - 일정 탭
   - 예산 탭
5. **사이드바 하단에서 실행 로그 확인 가능**

## 프로젝트 구조

```
test-agentic-service/
├── app/
│   ├── main.py                     # Streamlit 앱
│   ├── api/
│   │   └── main.py                 # FastAPI 백엔드
│   ├── retrieval/                  # RAG 시스템
│   │   ├── __init__.py
│   │   ├── search_service.py      # 하이브리드 검색 (Vector + Web)
│   │   ├── vector_store.py        # FAISS 로드/검색
│   │   ├── knowledge_loader.py    # 지식 데이터 로딩/청킹
│   │   ├── build_index.py         # 인덱스 빌드 스크립트
│   │   └── data/                  # 로컬 지식 데이터셋
│   ├── workflow/
│   │   ├── state.py               # TravelState 정의
│   │   ├── graph.py               # LangGraph 워크플로우
│   │   └── agents/
│   │       ├── city_recommender_agent.py
│   │       ├── flight_search_agent.py
│   │       ├── itinerary_agent.py
│   │       └── supervisor_agent.py
│   └── utils/
│       ├── config.py              # LLM 설정
│       └── logger.py              # 로깅 유틸리티
├── requirements.txt
├── run.sh
└── README.md
```

## MVP 특징

### 단순성
- Supervisor 기반 상태 분기 구조 (항공권 미가용 시 재검색 분기 포함)
- 각 에이전트는 독립적으로 동작
- 명확한 입력/출력 인터페이스

### 실행 가능성
- **RAG**: DuckDuckGo로 실시간 웹 정보 수집
- LLM으로 정보 통합 및 계획 생성
- 모든 기능이 즉시 실행 가능
- 에러 처리 및 로깅 포함

### 역할 분리
- 각 에이전트는 단일 책임 원칙 준수
- Supervisor는 흐름 제어만 담당
- 명확한 데이터 전달 구조

### 협업 루프(신규)
- `FlightSearchAgent`가 미가용 사유를 반환하면 `Supervisor`가 `needs_replan`을 설정해 `CityRecommenderAgent`에 재추천을 1회 요청
- `CityRecommenderAgent`는 `replan_reason`을 프롬프트에 반영해 항공 접근성이 더 높은 대안을 재제안
- 재추천 이후 `needs_replan=False`로 정리하고 항공권 단계를 재시도

### Memory 활용
- `TravelState`에 `decision_memory`, `constraints_memory`를 추가해 선택/분기 히스토리 축적
- Supervisor 분기 시 미가용 사유를 메모리에 기록하고 다음 검색에 재사용
- Agent B/C 프롬프트에 최근 메모리를 주입해 재시도/후속 일정 품질 보강

### ReAct 실행 표준화
- `tool_runner`에 ReAct 정책(system rule) 추가
- Tool 루프 로그를 `action/observation` 형식으로 구조화
- 최종 응답은 기존 JSON 스키마를 유지하도록 강제

### 최신 검증 결과 (2026-03-24)
- Streamlit UI와 FastAPI(`GET /api/health`, `POST /api/plan`) 모두 동일 워크플로우로 동작
- Streamlit은 `thread_id` 기반 이어서 재실행(멀티턴) 지원
- 테스트(현재 워크트리): `./venv/bin/python -m unittest discover -s tests` 기준 **28 tests, 2 failures**
- 실패 항목: `tests/test_supervisor_agent.py`의 기존 분기 가정(직접 다음 도시 전환)과 신규 재추천 루프 동작 차이

### Prompt Engineering 보강
- 각 에이전트에 소형 Few-shot 예시를 포함해 출력 형식 일관성 강화
- `rationale` 필드를 공통 도입해 짧은 판단 근거 표준화
- 필수 키 누락 시 JSON 리페어를 1회 수행하는 일관성 가드 적용

## RAG 시스템 상세

### 작동 방식
1. **Agent A (도시 추천)**
   - 쿼리: "{여행 주제} 여행 추천 도시 해외"
   - 최대 3개 검색 결과 수집
   - LLM이 검색 결과를 참고하여 도시 추천

2. **Agent B (항공권 검색)**
   - 쿼리: "서울 {도시명} 항공권 운항 여부 예약 가능 여부 평균 가격 항공사"
   - `search_flight_context` tool로 하이브리드 검색 컨텍스트 수집
   - tool observation을 응답 생성 및 가용성 판단(`search_context`)에 반영

3. **Agent C (일정 계획)**
   - 쿼리: "{도시명} {여행 주제} 여행 일정 추천 명소 맛집"
   - 최대 4개 검색 결과 수집
   - 실제 명소와 맛집 정보를 반영한 일정 생성

### 하이브리드 RAG 모드

- `RAG_MODE=hybrid` (기본): 벡터 검색 우선, 결과가 부족하면 웹 검색 보조
- `RAG_MODE=vector`: 벡터 검색 시도, 결과 부족/인덱스 미존재 시 웹 검색 fallback
- `RAG_MODE=web`: 웹 검색만 사용

추가 환경 변수:

- `VECTOR_TOP_K` (기본: `4`)
- `WEB_FALLBACK_MIN_RESULTS` (기본: `2`)

### 로깅 기능
- 각 에이전트의 입력/출력 로깅
- RAG 검색 쿼리 및 결과 로깅
- LLM 호출 및 응답 로깅
- JSON 파싱 과정 로깅
- UI에서 실시간 로그 확인

## 향후 개선 사항

- [ ] 실제 항공권 API 연동 (Skyscanner, Amadeus)
- [ ] 사용자가 도시 선택 가능하도록 개선
- [ ] 숙소 추천 기능 추가 (Booking.com API)
- [ ] 병렬 처리 지원
- [ ] 데이터베이스 연동 (여행 기록 저장)
- [ ] 더 복잡한 Supervisor 로직 (조건부 분기)
- [ ] RAG 고도화 (재랭킹, Pinecone 등 외부 벡터 스토어 확장)

## 문서 정합성 정리 (추가/삭제)

### 추가
- [x] Flight 단계 `search_flight_context` tool observation 연동 근거
- [x] LangGraph `MemorySaver`/`InMemoryStore` + UI `thread_id` 멀티턴 범위
- [x] 평가 체크포인트 대응 섹션(근거 파일 + known limitation)

### 삭제/수정
- [x] 과거 구현과 불일치한 Tool Calling 미적용 뉘앙스 문구 제거
- [x] 실제와 다른 테스트 수치(22 tests) -> 28 tests로 정정
- [x] 이미 구현된 FAISS를 "추가 예정"으로 표기한 항목 수정

## 라이선스

MIT License
