from sqlalchemy import TIMESTAMP, Column, Integer, String, text, Boolean
from .database import Base

class Posts(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default=text('true'))  # Assuming published is a boolean represented as an integer (1 for True, 0 for False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)