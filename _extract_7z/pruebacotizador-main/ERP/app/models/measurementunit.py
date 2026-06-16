from sqlalchemy import Column, Integer, String
from app.database import Base

class MeasurementUnit(Base):

    __tablename__ = "measurement_units"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(String)

    abbreviation = Column(
        String,
        unique=True
    )