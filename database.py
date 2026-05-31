import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncGenerator

from config import settings

# 创建异步引擎
async_engine = create_async_engine(
settings.DB_URL,
pool_size = 20,  # 生产级核心：初始核心连接池大小，防突发流量
max_overflow = 10,  # 生产级核心：允许在暴增并发时额外溢出的连接数
pool_recycle = 3600,  # 生产级核心：连接每 1 小时强制自动回收，防止连接老化
pool_pre_ping = True,  # 🎯 绝杀参数：每次拿连接前发心跳包，若已被阿里云断开则自动重连！
echo = False
)

# 创建异步会话工厂（SQLAlchemy 2.0原生）
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
            await session.close()  #显式添加异常后的关闭回收，多一层防泄漏保险


# FastAPI生命周期管理器（应用启动时自动建表）
@asynccontextmanager
async def lifespan(app: FastAPI):

    # 显式导入你的模型类，让 Base 感知到表结构
    import models # 💡 确保这里和你创建的文件名完全对齐

    logging.info("🚀 [Database] 正在检查并自动创建线上数据库表...")
    # 创建所有表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("✅ [Database] 数据表结构已完全就绪")

    yield

    # 应用关闭时释放资源
    logging.info("🔌 [Database] 正在安全释放线上数据库连接池...")
    await async_engine.dispose()
    logging.info("✅ [Database] 连接池资源已完全安全关闭")