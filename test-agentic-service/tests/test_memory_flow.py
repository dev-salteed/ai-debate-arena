import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.place_search_agent import PlaceSearchAgent
from workflow.agents.query_parser_agent import QueryParserAgent
from workflow.agents.recommendation_agent import RecommendationAgent


class MemoryFlowTests(unittest.TestCase):
    def test_query_parser_prompt_includes_memory_context(self):
        agent = QueryParserAgent()
        prompt = agent._create_prompt(
            {
                "user_query": "강남에서 조용한 카페 추천",
                "constraints_memory": {"region": "강남", "purpose": "작업"},
                "decision_memory": ["PLACE_SEARCH: 쿼리 3개, 근거 4개 수집"],
            }
        )
        self.assertIn("[이전 제약조건 메모리]", prompt)
        self.assertIn("region", prompt)
        self.assertIn("[최근 의사결정 메모리]", prompt)

    def test_place_search_prompt_includes_retry_guidance(self):
        agent = PlaceSearchAgent(enable_rag=True)
        prompt = agent._create_prompt(
            {
                "user_query": "홍대 데이트 카페",
                "parsed_query": {
                    "region": "홍대",
                    "subregion": "",
                    "venue_type": "카페",
                    "purpose": "데이트",
                    "atmosphere": ["조용한", "분위기 좋은"],
                    "price_range": "중간",
                    "must_have": [],
                    "avoid": ["시끄러운 곳"],
                    "search_queries": ["홍대 조용한 카페 데이트"],
                },
                "search_iterations": 1,
                "candidate_places": [],
                "decision_memory": ["SUPERVISOR: 후보 부족으로 검색 범위를 완화해 재검색"],
            }
        )
        self.assertIn("[재검색 지침]", prompt)
        self.assertIn("최근 의사결정 메모리", prompt)

    def test_recommendation_prompt_contains_candidate_place_details(self):
        agent = RecommendationAgent()
        prompt = agent._create_prompt(
            {
                "user_query": "성수 브런치 카페 추천",
                "parsed_query": {
                    "region": "성수",
                    "venue_type": "카페",
                    "purpose": "브런치",
                    "atmosphere": ["분위기 좋은"],
                    "price_range": "중간",
                    "must_have": [],
                    "avoid": [],
                },
                "search_brief": {"search_strategy": "브런치 중심 탐색"},
                "candidate_places": [
                    {
                        "name": "브런치 A",
                        "area": "성수",
                        "category": "브런치 카페",
                        "vibe_tags": ["분위기 좋은"],
                        "features": ["창가 좌석", "브런치 플레이트"],
                        "caution": "주말 대기 가능",
                        "source_note": "검색 결과 1",
                    }
                ],
            }
        )
        self.assertIn("브런치 A", prompt)
        self.assertIn("주말 대기 가능", prompt)


if __name__ == "__main__":
    unittest.main()
