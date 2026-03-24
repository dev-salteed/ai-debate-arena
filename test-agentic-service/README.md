# 저기어때 - 여행 계획 에이전틱 서비스

## 개요

**저기어때**는 사용자의 여행 주제만 입력하면 AI 에이전트들이 협력하여 완벽한 여행 계획을 자동으로 생성해주는 MVP 서비스입니다.

## 4.2 필수 기술 요소 구현 현황

| 항목 | 구현 상태 | 구현 내용 | 미구현/보강 필요 |
|------|----------|-----------|------------------|
| Prompt Engineering | 상당 구현 | 역할 기반 system prompt, 입력 구조화, JSON 출력 강제, Few-shot 예시, 필수 키 누락 시 JSON 보정 1회 | CoT/추론 단계의 정교한 표준화 |
| LangChain/LangGraph Agent | 부분~상당 구현 | Multi-Agent, LangGraph Supervisor 분기, Tool Calling(`bind_tools`) | 명시적 ReAct 포맷 표준화, Memory 활용 고도화 |
| RAG | 상당 구현 | 데이터 전처리/청킹, 임베딩, FAISS, 하이브리드 검색(벡터+웹) | 고도화 항목(재랭킹/멀티소스 등)만 잔존 |
| 서비스 개발/패키징 | 부분 구현 | Streamlit UI | FastAPI 백엔드(필수), Docker 배포(선택) |

### 근거 코드 위치
- Prompt/Agent: `app/workflow/agents/*`
- LangGraph 분기: `app/workflow/graph.py`, `app/workflow/agents/supervisor_agent.py`
- Tool Calling: `app/workflow/agents/tool_runner.py`
- RAG(FAISS/하이브리드): `app/retrieval/vector_store.py`, `app/retrieval/search_service.py`, `app/retrieval/knowledge_loader.py`

### 미구현 체크리스트 (우선순위)
- [x] P1 Prompt: Few-shot + 일관성 보정 템플릿
- [ ] P1 Memory: 상태 메모리 누적/재사용 고도화
- [ ] P1 FastAPI 백엔드: `GET /api/health`, `POST /api/plan`
- [ ] P2 ReAct: Tool 실행 흐름 포맷 표준화
- [ ] P3 Docker(선택): Streamlit + FastAPI 실행 환경

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
- 순차적 실행 구조 (복잡한 분기 없음)
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
   - 쿼리: "서울 {도시명} 항공권 평균 가격 항공사"
   - 최대 3개 검색 결과 수집
   - 실제 항공권 가격 참고하여 현실적인 견적 제공

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
- [ ] RAG 벡터 DB 추가 (FAISS, Pinecone)

## 라이선스

MIT License
