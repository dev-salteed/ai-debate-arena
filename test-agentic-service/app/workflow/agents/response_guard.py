"""JSON 응답 일관성 보정 유틸리티."""
from __future__ import annotations

import json
from typing import Iterable, Tuple


def extract_json_text(response_text: str) -> str:
    """코드블록이 포함된 응답에서 JSON 텍스트를 추출한다."""
    if "```json" in response_text:
        return response_text.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in response_text:
        return response_text.split("```", 1)[1].split("```", 1)[0].strip()
    return response_text.strip()


def missing_required_keys(payload: dict, required_keys: Iterable[str]) -> list[str]:
    """필수 키 누락 여부를 반환한다."""
    missing = []
    for key in required_keys:
        if key not in payload or payload.get(key) in (None, ""):
            missing.append(key)
    return missing


def parse_json(text: str) -> Tuple[dict, str]:
    """JSON 파싱 결과와 정제된 텍스트를 반환한다."""
    cleaned = extract_json_text(text)
    return json.loads(cleaned), cleaned

