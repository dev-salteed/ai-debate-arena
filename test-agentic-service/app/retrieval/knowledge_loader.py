"""Load and chunk local dining knowledge documents."""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 420, chunk_overlap: int = 80) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    if chunk_size <= 0:
        return [text]

    chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))
    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = end - chunk_overlap

    return chunks


def _load_json_records(file_path: Path) -> List[Dict]:
    with file_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return payload["records"]
        return [payload]
    return []


def _parse_front_matter(md_text: str) -> Tuple[Dict[str, str], str]:
    if not md_text.startswith("---\n"):
        return {}, md_text

    parts = md_text.split("---\n", 2)
    if len(parts) < 3:
        return {}, md_text

    metadata: Dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, parts[2]


def _load_markdown_record(file_path: Path) -> Dict:
    text = file_path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(text)
    return {
        "title": meta.get("title", file_path.stem),
        "region": meta.get("region", ""),
        "category": meta.get("category", "guide"),
        "source": meta.get("source", f"file:{file_path.name}"),
        "updated_at": meta.get("updated_at", datetime.now().strftime("%Y-%m-%d")),
        "text": body,
    }


def _record_to_documents(
    record: Dict,
    chunk_size: int = 420,
    chunk_overlap: int = 80,
) -> List[Document]:
    body = normalize_text(str(record.get("text", "")))
    if not body:
        return []

    chunks = chunk_text(body, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return []

    title = str(record.get("title", "Untitled")).strip()
    metadata_common = {
        "title": title,
        "region": str(record.get("region", "")).strip(),
        "category": str(record.get("category", "guide")).strip(),
        "source": str(record.get("source", "local-dataset")).strip(),
        "updated_at": str(
            record.get("updated_at", datetime.now().strftime("%Y-%m-%d"))
        ).strip(),
    }

    documents: List[Document] = []
    total = len(chunks)
    for index, chunk in enumerate(chunks):
        metadata = {
            **metadata_common,
            "chunk_index": index,
            "chunk_total": total,
        }
        documents.append(Document(page_content=chunk, metadata=metadata))
    return documents


def load_knowledge_documents(
    data_dir: Path = DEFAULT_DATA_DIR,
    chunk_size: int = 420,
    chunk_overlap: int = 80,
) -> List[Document]:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        logger.warning(f"[Vector RAG] 지식 데이터 폴더 없음: {data_dir}")
        return []

    documents: List[Document] = []
    json_files = sorted(data_dir.glob("*.json"))
    md_files = sorted(data_dir.glob("*.md"))

    for json_file in json_files:
        try:
            records = _load_json_records(json_file)
            for record in records:
                if isinstance(record, dict):
                    documents.extend(
                        _record_to_documents(
                            record=record,
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap,
                        )
                    )
        except Exception as exc:
            logger.error(f"[Vector RAG] JSON 로딩 실패: {json_file} ({exc})")

    for md_file in md_files:
        try:
            documents.extend(
                _record_to_documents(
                    record=_load_markdown_record(md_file),
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            )
        except Exception as exc:
            logger.error(f"[Vector RAG] Markdown 로딩 실패: {md_file} ({exc})")

    logger.info(
        f"[Vector RAG] 지식 문서 로드 완료: {len(documents)}개 "
        f"(json={len(json_files)}, md={len(md_files)})"
    )
    return documents
