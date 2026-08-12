# 文件路径: models.py
import datetime
from typing import List, Optional

from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database import Base


# ==========================================
# 表 1：用户表 (User)
# ==========================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)

    # 使用带时区 (timezone=True) 的 UTC 标准时间
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    chat_messages: Mapped[List["ChatMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ==========================================
# 表 2：文档向量表 (Document)
# ==========================================
class Document (Base):
    __tablename__ = "documents"
    id:Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(1024), nullable=False)
    metadata_info: Mapped[dict|None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))

# ==========================================
# 表 3：聊天记录表 (ChatMessage)
# ==========================================

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    user: Mapped["User"] = relationship(back_populates="chat_messages")