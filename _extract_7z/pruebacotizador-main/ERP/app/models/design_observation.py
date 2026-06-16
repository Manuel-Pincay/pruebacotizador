from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DesignObservation(Base):
    __tablename__ = "design_observations"

    id = Column(Integer, primary_key=True)
    design_tracking_id = Column(
        Integer,
        ForeignKey("design_tracking.id"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(Text)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    design_tracking = relationship("DesignTracking", back_populates="observations")
    user = relationship("User")
