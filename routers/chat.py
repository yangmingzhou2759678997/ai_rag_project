# 文件路径: routers/chat.py
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# 导入你自己写的各个基建模块
from database import get_db
from security import get_current_user
from schemas import ChatRequest
from services.agent_service import process_chat_request
from utils.logger import logger

# ==========================================
# 路由实例初始化
# ==========================================
router = APIRouter(prefix="/api/chat", tags=["AI对话模块"])


# ==========================================
# 核心接口：流式 AI 对话 (SSE)
# ==========================================
@router.post("/completions", summary="发起大模型流式对话")
async def chat_endpoint(
        request: ChatRequest,
        # 1. 🚀 关键修复：告诉 FastAPI，请给我准备一个后台任务篮子
        background_tasks: BackgroundTasks,

        # 依赖注入 A：保安查岗
        current_user=Depends(get_current_user),
        # 依赖注入 B：借用数据库连接
        db: AsyncSession = Depends(get_db)
):
    """
    接收用户提问，返回大模型流式打字机响应 (Server-Sent Events)
    """
    # 记录入口日志
    logger.info(f"📥 [路由层] 收到聊天请求 | 用户ID: {current_user.id} | 会话ID: {request.session_id}")
    logger.debug(f"用户提问内容: {request.query}")

    # 2. 移交大脑：把刚才拿到的 background_tasks 篮子，连同问题一起递给大脑处理
    response_generator = await process_chat_request(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        query=request.query,
        background_tasks=background_tasks  # 👈 递交后台任务筐
    )

    # 3. 流式响应：用 StreamingResponse 包装生成器返回给前端
    return StreamingResponse(
        content=response_generator,
        media_type="text/event-stream"
    )