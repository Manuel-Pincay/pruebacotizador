from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    full_name = Column(String)
    password = Column(String)
    role = Column(String, default="ventas")
    active = Column(Boolean, default=True)
    # Solo administradores configuran/reciben Telegram (UI en /users)
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_notify = Column(Boolean, default=False, nullable=False)
