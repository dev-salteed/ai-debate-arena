# 오늘 뭐먹지

자연어 요청을 받아 맛집과 카페를 추천하는 LangGraph 기반 에이전트 서비스입니다.  
사용자가 `강남에서 조용한 카페 추천해줘`처럼 입력하면, Query Parser, Search, RAG Processor, Recommendation 에이전트가 순차적으로 협업해 결과를 정리합니다.

## 핵심 기능

- 자연어 요청 파싱
  - 지역, 업종, 분위기, 목적, 가격대, 필수/회피 조건을 구조화합니다.
- 하이브리드 RAG 검색
  - 로컬 FAISS 지식과 DuckDuckGo 웹 검색을 조합합니다.
- 추천 후보 정제
  - 검색 결과를 근거 중심 후보 리스트로 압축합니다.
- 최종 추천 생성
  - 장소명, 위치, 특징, 추천 이유, 방문 팁, 후속 질문을 구조화해 반환합니다.
- 멀티턴 UX
  - 같은 `thread_id`로 이어서 재실행하면 제약 메모리와 의사결정 기록을 이어갑니다.

## 에이전트 구조

```text
사용자 요청
  -> Query Parser Agent
  -> Place Search Agent
  -> RAG Processor Agent
  -> Recommendation Agent
  -> UI / API 응답
```

Supervisor는 각 단계를 라우팅하고, 후보가 부족하면 검색 범위를 완화해 한 번 더 검색하도록 제어합니다.

## 기술 스택

- Streamlit
- FastAPI
- LangChain
- LangGraph
- Azure OpenAI
- DuckDuckGo Search
- FAISS

## 실행 방법

### 1. 환경 변수

루트 `.env`에 Azure OpenAI 설정을 넣습니다.

```bash
AOAI_API_KEY=...
AOAI_ENDPOINT=...
AOAI_DEPLOY_GPT4O=...
AOAI_API_VERSION=...
AOAI_EMBEDDING_DEPLOYMENT=...
```

### 2. 앱 실행

```bash
chmod +x run.sh
./run.sh
```

수동 실행:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
```

### 3. API 실행

```bash
source venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

엔드포인트:

- `GET /api/health`
- `POST /api/recommend`

예시 요청:

```json
{
  "user_query": "홍대에서 데이트하기 좋은 조용한 카페 추천해줘",
  "enable_rag": true,
  "max_search_iterations": 2
}
```

### 4. 로컬 벡터 인덱스 빌드

```bash
source venv/bin/activate
python -m app.retrieval.build_index --reset
```

## 테스트

```bash
source venv/bin/activate
python -m unittest discover -s tests
```

## 프로젝트 구조

```text
test-agentic-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── main.py
│   ├── retrieval/
│   │   ├── build_index.py
│   │   ├── data/dining_knowledge.json
│   │   ├── knowledge_loader.py
│   │   ├── search_service.py
│   │   └── vector_store.py
│   ├── utils/
│   │   ├── config.py
│   │   └── logger.py
│   └── workflow/
│       ├── graph.py
│       ├── state.py
│       └── agents/
│           ├── query_parser_agent.py
│           ├── place_search_agent.py
│           ├── rag_processor_agent.py
│           ├── recommendation_agent.py
│           ├── response_guard.py
│           ├── supervisor_agent.py
│           └── tool_runner.py
├── requirements.txt
├── run.sh
└── tests/
```
