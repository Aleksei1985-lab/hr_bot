from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    vacancy_id = Column(Integer, index=True)
    vacancy_title = Column(String)
    name = Column(String)
    surname = Column(String)
    phone = Column(String)
    age = Column(Integer)
    gender = Column(String)
    education = Column(String)
    telegram_id = Column(Integer, index=True)
    telegram_username = Column(String)
    timestamp = Column(String)
    language = Column(String)
    resume_file_id = Column(String, nullable=True)
    resume_filename = Column(String, nullable=True)

class VacancyPost(Base):
    __tablename__ = "vacancy_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    body = Column(Text, nullable=True)  # Тело сообщения для проверки уникальности
    timestamp = Column(DateTime, default=datetime.utcnow)
    channel_message_id = Column(Integer, nullable=True)
    channel_id = Column(Integer, nullable=True)