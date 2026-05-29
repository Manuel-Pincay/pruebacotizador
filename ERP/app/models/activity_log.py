from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime

from app.database import Base


class ActivityLog(Base):

    __tablename__ = "activity_logs"

    id = Column(
        Integer,
        primary_key=True
    )

    action = Column(String)

    description = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )