from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class LogEntryModel(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False, index=True)
    service = Column(String, nullable=False, index=True)
    level = Column(String, nullable=False)
    error_code = Column(String, nullable=True, index=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
