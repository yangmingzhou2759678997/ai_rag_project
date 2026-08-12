# 文件路径: routers/chat.py
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from services import memory_service
# 导入各个基建模块
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
        # 1. 告诉 FastAPI，给我准备一个后台任务篮子
        background_tasks: BackgroundTasks,

        # 依赖注入 A：检查/获取用户
        current_user=Depends(get_current_user),
        # 依赖注入 B：获得数据库连接
        db: AsyncSession = Depends(get_db)
):
    """
    接收用户提问，返回大模型流式打字机响应
    """
    # 记录入口日志
    logger.info(f" [路由层] 收到聊天请求 | 用户ID: {current_user.id} | 会话ID: {request.session_id}")
    logger.debug(f"用户提问内容: {request.query}")

    # 2. 移交核心中枢：把刚才拿到的 background_tasks 篮子，连同问题一起递给中枢
    response_generator = await process_chat_request(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        query=request.query,
        background_tasks=background_tasks  #  递交后台任务筐
    )

    # 3. 流式响应：用 StreamingResponse 包装生成器返回给前端
    return StreamingResponse(
        content=response_generator,
        media_type="text/event-stream"
    )


# ==========================================
#  1：获取历史会话列表
# ==========================================
@router.get("/sessions", summary="获取用户的历史会话列表")
async def get_sessions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    sessions = await memory_service.get_user_sessions(db, current_user.id)
    return {"code": 200, "data": sessions}

# ==========================================
#  2：点击侧边栏会话时，拉取该会话的所有聊天记录回显
# ==========================================
@router.get("/history/{session_id}", summary="获取特定会话的历史消息")
async def get_history(
    session_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 复用写好的历史记录函数，给前端渲染拉取前50条
    history = await memory_service.get_chat_history(db, session_id, window_size=50)
    return {"code": 200, "data": history}


# 新增：删除会话接口
@router.delete("/sessions/{session_id}", summary="删除指定会话")
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await memory_service.delete_session(db, session_id, current_user.id)
    return {"code": 200, "msg": "会话删除成功"}