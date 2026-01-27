import os
import logging
import streamlit as st
from sqlalchemy import create_engine
from contextlib import contextmanager

from database.model import Base

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH")
CONNECTION_NAME = "sqlite_db"


class DatabaseSession:

    # Singleton 패턴 적용
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseSession, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        logger.info("데이터베이스 스키마 초기화 중...")
        engine = create_engine(f"sqlite:///{DB_PATH}")
        Base.metadata.create_all(engine)
        logger.info("데이터베이스 초기화 완료")

    # st.cache_resource 데코레이터를 사용하여 Streamlit 앱이 실행되는 동안 동일한 리소스를 공유
    @st.cache_resource
    def get_connection(_self):
        return st.connection(CONNECTION_NAME, type="sql", url=f"sqlite:///{DB_PATH}")

    # 데이터베이스 작업을 위한 세션 반환
    def get_session(self):
        return self.get_connection().session

    # with 문을 사용하기 위해 contextmanager 데코레이터 추가
    @contextmanager
    def get_db_session(self):
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Singleton Instance 생성
db_session = DatabaseSession()
