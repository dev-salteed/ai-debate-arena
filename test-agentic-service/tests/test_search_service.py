import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from retrieval.search_service import (
    merge_contexts,
    search_place_context_tool,
    search_with_context,
)


class SearchServiceTests(unittest.TestCase):
    @patch("retrieval.search_service.search_with_context")
    def test_place_context_tool_calls_hybrid_search(self, mock_search_with_context):
        mock_search_with_context.return_value = "맛집 컨텍스트 결과"
        result = search_place_context_tool.invoke(
            {"query": "강남 조용한 카페", "max_results": 4}
        )
        mock_search_with_context.assert_called_once_with(
            query="강남 조용한 카페",
            max_results=4,
        )
        self.assertEqual(result, "맛집 컨텍스트 결과")

    @patch("retrieval.search_service.search_web")
    @patch("retrieval.search_service.retrieve_with_vector")
    def test_hybrid_skips_web_when_vector_results_are_sufficient(
        self,
        mock_retrieve_with_vector,
        mock_search_web,
    ):
        with patch.dict(
            os.environ,
            {"RAG_MODE": "hybrid", "VECTOR_TOP_K": "4", "WEB_FALLBACK_MIN_RESULTS": "2"},
            clear=False,
        ):
            mock_retrieve_with_vector.return_value = [
                {
                    "title": "강남 조용한 카페 찾는 법",
                    "body": "골목권 로스터리 카페를 함께 보세요.",
                    "href": "internal:gangnam-quiet-cafes",
                },
                {
                    "title": "조용한 카페 검색 확장 팁",
                    "body": "콘센트, 작업하기 좋은 키워드를 같이 넣습니다.",
                    "href": "internal:quiet-cafe-query-guide",
                },
            ]

            context = search_with_context("강남 조용한 카페", max_results=5)
            mock_search_web.assert_not_called()
            self.assertIn("로컬 다이닝 지식", context)
            self.assertIn("강남 조용한 카페 찾는 법", context)

    @patch("retrieval.search_service.search_web")
    @patch("retrieval.search_service.retrieve_with_vector")
    def test_hybrid_falls_back_to_web_when_vector_results_are_insufficient(
        self,
        mock_retrieve_with_vector,
        mock_search_web,
    ):
        with patch.dict(
            os.environ,
            {"RAG_MODE": "hybrid", "VECTOR_TOP_K": "4", "WEB_FALLBACK_MIN_RESULTS": "2"},
            clear=False,
        ):
            mock_retrieve_with_vector.return_value = [
                {"title": "벡터 결과", "body": "로컬 요약", "href": "internal:vector"}
            ]
            mock_search_web.return_value = [
                {"title": "웹 결과", "body": "최신 후기", "href": "https://example.com/place"}
            ]

            context = search_with_context("홍대 데이트 카페", max_results=3)
            mock_search_web.assert_called_once()
            self.assertIn("웹 검색 결과", context)
            self.assertIn("웹 결과", context)

    def test_merge_contexts_keeps_body_and_source_format(self):
        vector_results = [
            {"title": "벡터 타이틀", "body": "벡터 본문", "href": "internal:vector-source"}
        ]
        web_results = [
            {"title": "웹 타이틀", "body": "웹 본문", "href": "https://example.com/source"}
        ]

        context = merge_contexts(vector_results=vector_results, web_results=web_results)
        self.assertIn("벡터 본문", context)
        self.assertIn("웹 본문", context)
        self.assertIn("출처: internal:vector-source", context)
        self.assertIn("출처: https://example.com/source", context)


if __name__ == "__main__":
    unittest.main()
