from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.session import Base


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True)
    company_name = Column(String(255), nullable=True)
    logo_url = Column(Text, nullable=True)
    primary_color = Column(String(20), nullable=True, default="#6D28D9")
    secondary_color = Column(String(20), nullable=True, default="#FFFFFF")
    brand_voice = Column(Text, nullable=True)  # e.g. "luxury, professional, elegant"
    tagline = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    extra = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client = relationship("Client", backref="brand_kit_obj")
