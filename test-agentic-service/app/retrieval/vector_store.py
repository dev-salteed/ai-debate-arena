"""FAISS vector store utilities for local dining knowledge."""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

try:
    from utils.config import get_embeddings
except ModuleNotFoundError:
    from app.utils.config import get_embeddings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
INDEX_DIR = BASE_DIR / "index"
INDEX_NAME = "dining_knowledge"

_vector_store: Optional[FAISS] = None


def _index_exists(index_dir: Path = INDEX_DIR, index_name: str = INDEX_NAME) -> bool:
    return (index_dir / f"{index_name}.faiss").exists() and (
        index_dir / f"{index_name}.pkl"
    ).exists()


def load_vector_store(force_reload: bool = False) -> Optional[FAISS]:
    global _vector_store

    if _vector_store is not None and not force_reload:
        return _vector_store

    if not _index_exists():
        logger.warning(
            f"[Vector RAG] 인덱스 파일이 없습니다: {INDEX_DIR / (INDEX_NAME + '.faiss')}"
        )
        return None

    try:
        embeddings = get_embeddings()
        _vector_store = FAISS.load_local(
            folder_path=str(INDEX_DIR),
            index_name=INDEX_NAME,
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("[Vector RAG] 인덱스 로드 완료")
        return _vector_store
    except Exception as exc:
        logger.error(f"[Vector RAG] 인덱스 로드 실패: {exc}")
        return None


def build_vector_index(
    documents: List[Document],
    index_dir: Path = INDEX_DIR,
    index_name: str = INDEX_NAME,
) -> int:
    if not documents:
        raise ValueError("인덱싱할 문서가 없습니다.")

    index_dir.mkdir(parents=True, exist_ok=True)
    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)
    vector_store.save_local(folder_path=str(index_dir), index_name=index_name)

    logger.info(f"[Vector RAG] 인덱스 저장 완료: {index_dir} ({len(documents)}개 문서)")
    return len(documents)


def retrieve(query: str, k: int = 4) -> List[Dict[str, str]]:
    store = load_vector_store()
    if store is None:
        return []

    try:
        results = store.similarity_search_with_score(query=query, k=max(1, k))
    except Exception as exc:
        logger.error(f"[Vector RAG] 검색 실패: {exc}")
        return []

    formatted: List[Dict[str, str]] = []
    for doc, score in results:
        metadata = doc.metadata or {}
        title = metadata.get("title") or metadata.get("region") or "로컬 다이닝 지식"
        body = (doc.page_content or "").strip()
        if not body:
            continue

        source = metadata.get("source", "local-knowledge")
        region = metadata.get("region", "")
        category = metadata.get("category", "")
        updated_at = metadata.get("updated_at", "")
        score_text = f"{float(score):.4f}"
        extra = ", ".join(
            [value for value in [region, category, updated_at, f"score={score_text}"] if value]
        )
        href = f"{source} ({extra})" if extra else source
        formatted.append({"title": title, "body": body, "href": href})

    logger.info(f"[Vector RAG] 검색 완료: {len(formatted)}개")
    return formatted
