from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import ChatMessage
from utils.logger import logger


# ==========================================
# 核心功能 1：保存单条聊天记录到数据库
# ==========================================
async def save_message(db: AsyncSession, user_id: int, session_id: str, role: str, content: str):
    """
    保存聊天记录
    作用：不管是用户说的话，还是大模型回复的话，统统通过这个函数存入 PostgreSQL。
    """
    try:
        # 1. 实例化一个 ChatMessage 对象，就像填表一样把参数塞进去
        new_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content
        )

        # 2. 把填好的表单丢进数据库的“暂存区”
        db.add(new_message)

        # 3. 提交事务，真正写入硬盘
        await db.commit()

        # 4. 刷新一下对象，确保如果后续要用，能拿到数据库自动生成的 ID
        await db.refresh(new_message)

    except Exception as e:
        # 5. 如果写入失败，必须回滚事务，防止数据库死锁，并记录日志
        await db.rollback()
        logger.error(f" 保存聊天记录失败 [session_id: {session_id}]: {e}")
        raise e


# ==========================================
# 核心功能 2：滑动窗口读取历史记录
# ==========================================
async def get_chat_history(db: AsyncSession, session_id: str, window_size: int = 10) -> list[dict]:
    """
    获取滑动窗口历史记录
    作用：拉取最近的 10 条对话记录，喂给大模型，让它拥有记忆。
    """
    try:
        # 1. 构建查询语句：去 ChatMessage 表里找数据
        # 条件：session_id 必须对得上
        # 排序：按创建时间倒序排 (desc)。为什么？因为我们要拿“最新”的聊天记录！
        # 限制：只拿最近的 window_size 条 (比如最近 10 条)
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(window_size)
        )

        # 2. 执行查询，拿到结果
        result = await db.execute(stmt)

        # 3. 把数据库结果解析成 Python 的对象列表
        # 注意：此时拿到的列表是最新的在最前面，比如 [第10句, 第9句, 第8句...]
        recent_messages = result.scalars().all()

        if not recent_messages:
            return []

        # 4. 核心算法：反转列表
        # 大模型阅读历史记录的习惯和人类一样，必须是从旧到新（正序）。
        # 所以我们用 Python 的切片魔法 [::-1]，把 [10, 9, 8] 翻转成 [8, 9, 10]。
        ordered_messages = recent_messages[::-1]

        # 5. 组装成 OpenAI / 大模型认识的标准 JSON 格式
        # 也就是把对象变成 [{"role": "user", "content": "你好"}, ...] 这种格式
        history_list = []
        for msg in ordered_messages:
            history_list.append({
                "role": msg.role,
                "content": msg.content
            })

        return history_list

    except Exception as e:
        logger.error(f" 拉取历史记录失败 [session_id: {session_id}]: {e}")
        return []




# ==========================================
# 核心功能 3：获取用户的所有历史会话列表 (修复多会话缺失)
# ==========================================
async def get_user_sessions(db: AsyncSession, user_id: int) -> list[str]:
    """
    作用：供前端侧边栏调用，列出该用户过去所有的对话 session_id。
    """
    try:
        # 按时间倒序查询，保证最近聊过的会话排在最上面
        stmt = (
            select(ChatMessage.session_id)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
        )
        result = await db.execute(stmt)

        # 使用 Python 的 dict.fromkeys 来实现去重，同时完美保留时间倒序的顺序
        session_ids = list(dict.fromkeys(result.scalars().all()))
        return session_ids
    except Exception as e:
        logger.error(f" 拉取会话列表失败 [user_id: {user_id}]: {e}")


# ==========================================
# 核心功能 4：删除用户历史会话列表
# ==========================================
from sqlalchemy import delete

# 新增：删除会话函数
async def delete_session(db: AsyncSession, session_id: str, user_id: int):
    """删除指定用户的指定会话及其所有消息"""
    # 删除该会话的所有消息
    await db.execute(
        delete(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.user_id == user_id)
    )
    await db.commit()
    logger.info(f" [内存服务] 成功删除会话 | 会话ID: {session_id} | 用户ID: {user_id}")