"""로컬 지식 데이터로 FAISS 인덱스를 빌드하는 스크립트."""
from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

try:
    from retrieval.knowledge_loader import load_knowledge_documents
    from retrieval.vector_store import INDEX_DIR, INDEX_NAME, build_vector_index
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from app.retrieval.knowledge_loader import load_knowledge_documents
    from app.retrieval.vector_store import INDEX_DIR, INDEX_NAME, build_vector_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local FAISS index for 오늘 뭐해?")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(Path(__file__).resolve().parent / "data"),
        help="지식 데이터 폴더 경로 (JSON/Markdown)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=400,
        help="청크 크기 (문자 단위)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=80,
        help="청크 오버랩 (문자 단위)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="기존 인덱스를 삭제하고 재생성",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        logging.error(f"지식 데이터 폴더가 없습니다: {data_dir}")
        return 1

    if args.reset and INDEX_DIR.exists():
        logging.info(f"기존 인덱스 삭제: {INDEX_DIR}")
        shutil.rmtree(INDEX_DIR)

    logging.info("지식 문서 로딩 중...")
    documents = load_knowledge_documents(
        data_dir=data_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    if not documents:
        logging.error("인덱싱할 문서가 없습니다. 데이터 파일을 확인하세요.")
        return 1

    logging.info(f"FAISS 인덱스 생성 중... (문서 수: {len(documents)})")
    build_vector_index(documents=documents, index_dir=INDEX_DIR, index_name=INDEX_NAME)

    logging.info("인덱스 빌드 완료")
    logging.info(f"- 저장 위치: {INDEX_DIR}")
    logging.info(f"- 인덱스 이름: {INDEX_NAME}")
    logging.info("다음 실행부터 로컬 벡터 검색이 자동 사용됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
