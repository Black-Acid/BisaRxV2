from sqlalchemy import (
    Column, Integer, ForeignKey, String, Text,
    DateTime, Boolean, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from enum import Enum
import uuid
from passlib.context import CryptContext

from database import Base


class SenderType(str, Enum):
    USER = "user"
    AI = "ai"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sessions = relationship("ChatSessionModel", back_populates="user")
    
    def password_verification(self, password):
        return pwd_context.verify(password, self.hashed_password)


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_title = Column(String(255))
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("UserModel", back_populates="sessions")
    messages = relationship("MessageModel", back_populates="session")


class MessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)

    sender = Column(
        SQLEnum(SenderType, name="sender_type_enum"),
        nullable=False
    )

    message_text = Column(Text, nullable=False)
    is_emergency = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    session = relationship("ChatSessionModel", back_populates="messages")
    feedback = relationship("FeedbackModel", back_populates="message", uselist=False)


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    rating = Column(Integer)
    comment = Column(Text)
    created_at = Column(DateTime, default=func.now())

    message = relationship("MessageModel", back_populates="feedback")
