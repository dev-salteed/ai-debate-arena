import datetime
import json
import logging
from typing import List, Optional, Tuple, Dict

from database.model import Debate
from database.session import db_session

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    pass


class DebateRepository:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DebateRepository, cls).__new__(cls)
        return cls._instance

    # docs도 저장할 수 있도록 변경
    def save(
        self, topic: str, rounds: int, messages: List[Dict], docs: Optional[Dict] = None
    ) -> bool:
        try:
            with db_session.get_db_session() as session:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                messages_json = json.dumps(messages, ensure_ascii=False)

                # docs를 JSON 형태로 변환
                # ensure_ascii=False: 한글이 유니코드로 변환되지 않도록 설정
                docs_json = json.dumps(docs, ensure_ascii=False) if docs else None

                # docs 추가
                debate = Debate(
                    topic=topic,
                    date=now,
                    rounds=rounds,
                    messages=messages_json,
                    docs=docs_json,
                )
                session.add(debate)
            return True
        except Exception as e:
            logger.error(f"토론 저장 중 오류 발생: {str(e)}")
            raise RepositoryError(f"토론 저장 오류: {str(e)}") from e

    # 리스팅에는 docs가 필요하지 않으므로 제외
    def fetch(self) -> List[Tuple[int, str, str, int]]:
        try:
            with db_session.get_db_session() as session:
                debates = (
                    session.query(Debate.id, Debate.topic, Debate.date, Debate.rounds)
                    .order_by(Debate.date.desc())
                    .all()
                )
                return [(d.id, d.topic, d.date, d.rounds) for d in debates]
        except Exception as e:
            logger.error(f"토론 이력 조회 중 오류 발생: {str(e)}")
            raise RepositoryError(f"토론 이력 조회 오류: {str(e)}") from e

    # docs를 추가하여 반환
    def fetch_by_id(
        self, debate_id: int
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[Dict]]:
        try:
            with db_session.get_db_session() as session:
                debate = session.query(Debate).filter(Debate.id == debate_id).first()

                if debate:
                    messages = json.loads(debate.messages)
                    # json문자열을 파이썬 딕셔너리로 변환
                    docs = json.loads(debate.docs) if debate.docs else {}
                    return debate.topic, messages, docs
                return None, None, None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 디코딩 오류: {str(e)}")
            raise RepositoryError(f"토론 데이터 변환 오류: {str(e)}") from e
        except Exception as e:
            logger.error(f"토론 불러오기 중 오류 발생: {str(e)}")
            raise RepositoryError(f"토론 불러오기 오류: {str(e)}") from e

    def delete_by_id(self, debate_id: int) -> bool:
        try:
            with db_session.get_db_session() as session:
                result = session.query(Debate).filter(Debate.id == debate_id).delete()
                return result > 0
        except Exception as e:
            logger.error(f"토론 삭제 중 오류 발생: {str(e)}")
            raise RepositoryError(f"토론 삭제 오류: {str(e)}") from e

    def delete_all(self) -> int:
        try:
            with db_session.get_db_session() as session:
                result = session.query(Debate).delete()
                return result
        except Exception as e:
            logger.error(f"전체 토론 삭제 중 오류 발생: {str(e)}")
            raise RepositoryError(f"전체 토론 삭제 오류: {str(e)}") from e


debate_repository = DebateRepository()
