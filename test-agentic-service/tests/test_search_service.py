import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from retrieval.search_service import merge_contexts, search_with_context


class SearchServiceTests(unittest.TestCase):
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
                    "title": "도쿄 겨울 미식 여행 가이드",
                    "body": "도쿄 겨울 여행에서는 권역별 동선 구성이 중요하다.",
                    "href": "internal:tokyo-guide",
                },
                {
                    "title": "도쿄 5일 일정 구성 원칙",
                    "body": "도착일과 출국일은 가볍게 배치한다.",
                    "href": "internal:tokyo-itinerary",
                },
            ]

            context = search_with_context("도쿄 겨울 미식", max_results=5)

            mock_search_web.assert_not_called()
            self.assertIn("벡터 검색 결과", context)
            self.assertIn("도쿄 겨울 미식 여행 가이드", context)

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
                {
                    "title": "벡터 결과 1",
                    "body": "벡터 검색 결과 본문",
                    "href": "internal:vector-1",
                }
            ]
            mock_search_web.return_value = [
                {
                    "title": "웹 결과 1",
                    "body": "웹 검색 결과 본문",
                    "href": "https://example.com/travel",
                }
            ]

            context = search_with_context("도쿄 여행", max_results=3)

            mock_search_web.assert_called_once()
            self.assertIn("벡터 검색 결과", context)
            self.assertIn("웹 검색 결과", context)
            self.assertIn("웹 결과 1", context)

    @patch("retrieval.search_service.search_web")
    @patch("retrieval.search_service.retrieve_with_vector")
    def test_vector_mode_gracefully_falls_back_to_web_when_index_missing(
        self,
        mock_retrieve_with_vector,
        mock_search_web,
    ):
        with patch.dict(
            os.environ,
            {"RAG_MODE": "vector", "VECTOR_TOP_K": "4", "WEB_FALLBACK_MIN_RESULTS": "2"},
            clear=False,
        ):
            # 인덱스 없음/손상 상황을 빈 결과로 모델링
            mock_retrieve_with_vector.return_value = []
            mock_search_web.return_value = [
                {
                    "title": "웹 보조 결과",
                    "body": "인덱스가 없어도 웹 검색으로 보조된다.",
                    "href": "https://example.com/fallback",
                }
            ]

            context = search_with_context("파리 문화 여행", max_results=4)

            mock_search_web.assert_called_once()
            self.assertIn("웹 검색 결과", context)
            self.assertIn("웹 보조 결과", context)

    @patch("retrieval.search_service.search_web")
    @patch("retrieval.search_service.retrieve_with_vector")
    def test_hybrid_falls_back_to_web_when_vector_raises_exception(
        self,
        mock_retrieve_with_vector,
        mock_search_web,
    ):
        with patch.dict(
            os.environ,
            {"RAG_MODE": "hybrid", "VECTOR_TOP_K": "4", "WEB_FALLBACK_MIN_RESULTS": "2"},
            clear=False,
        ):
            mock_retrieve_with_vector.side_effect = RuntimeError("index corrupted")
            mock_search_web.return_value = [
                {
                    "title": "웹 fallback",
                    "body": "벡터 예외 상황에서 웹 검색 대체",
                    "href": "https://example.com/corrupt-index-fallback",
                }
            ]

            context = search_with_context("방콕 야시장 일정", max_results=3)

            mock_search_web.assert_called_once()
            self.assertIn("웹 검색 결과", context)
            self.assertIn("웹 fallback", context)

    def test_merge_contexts_keeps_body_and_source_format(self):
        vector_results = [
            {
                "title": "벡터 타이틀",
                "body": "벡터 본문 텍스트",
                "href": "internal:vector-source",
            }
        ]
        web_results = [
            {
                "title": "웹 타이틀",
                "body": "웹 본문 텍스트",
                "href": "https://example.com/source",
            }
        ]

        context = merge_contexts(vector_results=vector_results, web_results=web_results)

        self.assertIn("벡터 본문 텍스트", context)
        self.assertIn("웹 본문 텍스트", context)
        self.assertIn("출처: internal:vector-source", context)
        self.assertIn("출처: https://example.com/source", context)


if __name__ == "__main__":
    unittest.main()
