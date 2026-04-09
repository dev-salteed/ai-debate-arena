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
    dedupe_results,
    merge_contexts,
    search_outing_candidates,
    search_outing_context_tool,
    search_with_context,
)


class SearchServiceTests(unittest.TestCase):
    @patch("retrieval.search_service.search_with_context")
    def test_outing_context_tool_calls_context_search(self, mock_search_with_context):
        mock_search_with_context.return_value = "상황형 컨텍스트 결과"

        result = search_outing_context_tool.invoke({"query": "성수 비 오는 날 데이트 추천", "max_results": 4})

        mock_search_with_context.assert_called_once_with(query="성수 비 오는 날 데이트 추천", max_results=4)
        self.assertEqual(result, "상황형 컨텍스트 결과")

    def test_dedupe_results_prefers_higher_score_duplicate(self):
        deduped = dedupe_results(
            [
                {"title": "성수 전시", "body": "A", "href": "https://example.com/a?utm_source=x", "score": 2.0, "rank": 2},
                {"title": "성수 전시", "body": "B", "href": "https://example.com/a", "score": 6.0, "rank": 1},
            ]
        )

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["body"], "B")

    @patch("retrieval.search_service.search_web")
    def test_search_outing_candidates_merges_and_dedupes_queries(self, mock_search_web):
        mock_search_web.side_effect = [
            [
                {"title": "성수 전시", "body": "실내 데이트", "href": "https://example.com/a"},
                {"title": "성수 카페", "body": "조용한 카페", "href": "https://example.com/b"},
            ],
            [
                {"title": "성수 전시", "body": "실내 데이트", "href": "https://example.com/a?utm_source=dup"},
            ],
        ]

        results = search_outing_candidates(
            queries=["성수 전시 추천", "성수 카페 추천"],
            max_results_per_query=3,
            context_terms=["성수", "데이트", "비"],
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["href"], "https://example.com/a")

    @patch("retrieval.search_service.search_web")
    @patch("retrieval.search_service.retrieve_with_vector")
    def test_web_mode_uses_web_results(self, mock_retrieve_with_vector, mock_search_web):
        with patch.dict(os.environ, {"RAG_MODE": "web"}, clear=False):
            mock_search_web.return_value = [{"title": "웹 결과", "body": "본문", "href": "https://example.com"}]
            context = search_with_context("성수 데이트", max_results=3)

        mock_retrieve_with_vector.assert_not_called()
        self.assertIn("웹 검색 결과", context)
        self.assertIn("웹 결과", context)

    def test_merge_contexts_keeps_body_and_source_format(self):
        vector_results = [{"title": "로컬 타이틀", "body": "로컬 본문", "href": "internal:local"}]
        web_results = [{"title": "웹 타이틀", "body": "웹 본문", "href": "https://example.com/source"}]

        context = merge_contexts(vector_results=vector_results, web_results=web_results)

        self.assertIn("로컬 본문", context)
        self.assertIn("웹 본문", context)
        self.assertIn("출처: internal:local", context)
        self.assertIn("출처: https://example.com/source", context)


if __name__ == "__main__":
    unittest.main()
