"""FAISS 기반 로컬 벡터 스토어 유틸리티."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

try:
    from utils.config import get_embeddings
except ModuleNotFoundError:  # pragma: no cover - package path fallback
    from app.utils.config import get_embeddings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
INDEX_DIR = BASE_DIR / "index"
INDEX_NAME = "outing_knowledge"

_vector_store: Optional[FAISS] = None


def _index_exists(index_dir: Path = INDEX_DIR, index_name: str = INDEX_NAME) -> bool:
    """FAISS 인덱스 파일 존재 여부를 확인한다."""
    faiss_file = index_dir / f"{index_name}.faiss"
    pkl_file = index_dir / f"{index_name}.pkl"
    return faiss_file.exists() and pkl_file.exists()


def load_vector_store(force_reload: bool = False) -> Optional[FAISS]:
    """
    로컬 FAISS 인덱스를 로드한다.

    Returns:
        FAISS 인스턴스 또는 None
    """
    global _vector_store

    if _vector_store is not None and not force_reload:
        return _vector_store

    if not _index_exists():
        logger.warning(f"[오늘 뭐해?] 인덱스 파일이 없습니다: {INDEX_DIR / (INDEX_NAME + '.faiss')}")
        return None

    try:
        embeddings = get_embeddings()
        _vector_store = FAISS.load_local(
            folder_path=str(INDEX_DIR),
            index_name=INDEX_NAME,
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("[오늘 뭐해?] 인덱스 로드 완료")
        return _vector_store
    except Exception as exc:  # pragma: no cover - optional path
        logger.error(f"[오늘 뭐해?] 인덱스 로드 실패: {exc}")
        return None


def build_vector_index(
    documents: List[Document],
    index_dir: Path = INDEX_DIR,
    index_name: str = INDEX_NAME,
) -> int:
    """문서 리스트로 FAISS 인덱스를 생성/저장한다."""
    if not documents:
        raise ValueError("인덱싱할 문서가 없습니다.")

    index_dir.mkdir(parents=True, exist_ok=True)

    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)
    vector_store.save_local(folder_path=str(index_dir), index_name=index_name)

    logger.info(f"[오늘 뭐해?] 인덱스 저장 완료: {index_dir} ({len(documents)}개 문서)")
    return len(documents)


def retrieve(query: str, k: int = 4) -> List[Dict[str, str]]:
    """
    벡터 유사도 검색을 수행한다.

    Returns:
        [{"title": "...", "body": "...", "href": "..."}]
    """
    store = load_vector_store()
    if store is None:
        return []

    try:
        results = store.similarity_search_with_score(query=query, k=max(1, k))
    except Exception as exc:  # pragma: no cover - optional path
        logger.error(f"[오늘 뭐해?] 검색 실패: {exc}")
        return []

    formatted: List[Dict[str, str]] = []
    for doc, score in results:
        metadata = doc.metadata or {}
        title = metadata.get("title") or metadata.get("region") or "로컬 지식"
        source = metadata.get("source", "local-knowledge")
        body = (doc.page_content or "").strip()
        if not body:
            continue

        category = metadata.get("category", "")
        updated_at = metadata.get("updated_at", "")
        score_text = f"{float(score):.4f}"
        extra = ", ".join([x for x in [category, updated_at, f"score={score_text}"] if x])
        href = f"{source} ({extra})" if extra else source

        formatted.append(
            {
                "title": title,
                "body": body,
                "href": href,
            }
        )

    logger.info(f"[오늘 뭐해?] 벡터 검색 완료: {len(formatted)}개")
    return formatted
