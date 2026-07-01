import enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.session import Base


class QualityMode(str, enum.Enum):
    economy = "economy"
    standard = "standard"
    premium = "premium"


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    brand_kit = Column(JSON, default=dict)
    default_mode = Column(SAEnum(QualityMode), default=QualityMode.economy)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("Job", back_populates="client")
