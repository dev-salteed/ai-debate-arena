from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Debate(Base):
    __tablename__ = "debates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String, nullable=False)
    date = Column(String, nullable=False)
    rounds = Column(Integer, nullable=False)
    messages = Column(Text, nullable=False)
    docs = Column(Text, nullable=True)  # RAG 검색 결과 저장
