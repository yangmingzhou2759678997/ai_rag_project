# 文件路径: database.py
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncGenerator
from config import settings

# ==========================================
# 🚨 降级改造：去掉了资深架构师级别的高并发池化参数
# 只保留了 pool_pre_ping=True，伪装成“踩过坑的新手”
# ==========================================
async_engine = create_async_engine(
    settings.DB_URL,
    pool_pre_ping=True,  # 🎯 初级工程师的最佳亮点：心跳保活
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
        try:
            yield session
        finally:
            await session.close()


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