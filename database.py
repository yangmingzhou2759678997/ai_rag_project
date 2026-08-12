# 文件路径: database.py
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncGenerator
from config import settings

# 创建数据库引擎
async_engine = create_async_engine(
    settings.DB_URL,
    pool_pre_ping=True,  # 心跳保活
    echo=False
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


# 基础模型类
class Base(DeclarativeBase):
    pass


# 数据库依赖
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
            yield session



# FastAPI生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表
    import models
    async with async_engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    yield

    # 停止时清理资源
    await async_engine.dispose()