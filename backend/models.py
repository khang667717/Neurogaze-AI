# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from .database import Base
import datetime

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    user_id = Column(String, default="default_user")

class SessionAggregate(Base):
    __tablename__ = "session_aggregates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    focus_score = Column(Float, default=0.0)
    active_ratio = Column(Float, default=0.0)
