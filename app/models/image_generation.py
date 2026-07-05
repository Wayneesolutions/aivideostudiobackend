import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ImageGeneration(Base):
    __tablename__ = "image_generations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    style = Column(String(100), nullable=True)
    ratio = Column(String(20), nullable=True)
    resolution = Column(String(50), nullable=True)
    image_url = Column(Text, nullable=False)
    reference_image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", backref="image_generations")
