from sqlalchemy import TIMESTAMP, Column, ForeignKey, Integer, String, text, Boolean
from .database import Base
from sqlalchemy.orm import relationship

class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    is_active = Column(Boolean, server_default=text('true'), nullable=False)

class Posts(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default=text('true'))  # Assuming published is a boolean represented as an integer (1 for True, 0 for False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Assuming user_id is a foreign key referencing the users table
    user = relationship("Users") # Assuming you have a Users model with a 'posts' relationship defined
    
       
  # Assuming is_active is a boolean represented as an integer (1 for True, 0 for False)