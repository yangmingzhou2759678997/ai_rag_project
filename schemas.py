from pydantic import BaseModel, Field
from typing import Optional


# ==========================================
# 第一部分：认证与用户模块 (Auth Schemas)
# ==========================================
# 1. 定义前端调用“注册接口”时，必须传给我们的 JSON 格式
class UserCreate(BaseModel):
    # Field(...) 表示这个字段是必填的
    # min_length 和 max_length 是 Pydantic 强大的自动校验功能。如果前端传了 2 个字的用户名，直接会被我们昨天的全局异常拦截器拦截报 422 错误！
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="明文密码")


# 2. 定义后端查询完数据库后，返回给前端的“用户信息”格式
class UserResponse(BaseModel):
    id: int
    username: str

    # 3. 核心机制：允许 Pydantic 直接读取 SQLAlchemy 的 ORM 模型对象 (models.User)
    # 因为数据库查询出来的结果是一个对象 (user.id)，而不是字典 (user["id"])，加了这句话，Pydantic 就能自动翻译。
    class Config:
        from_attributes = True


# 4. 定义登录成功后，返回给前端的 JWT Token 格式
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ==========================================
# 第二部分：AI 聊天模块 (Chat Schemas) - 本次核心新增
# ==========================================
# 5. 定义前端调用“AI对话接口”时，发给我们的 JSON 格式
class ChatRequest(BaseModel):
    # 用户真实的提问内容，比如 "帮我查一下机械臂怎么修"
    query: str = Field(..., description="用户发出的提问内容")

    # 6. 核心字段：多轮对话记忆标识。
    # 前端必须把之前的 session_id 传回来，我们的 memory_service 才知道去数据库捞哪一段历史记录
    session_id: str = Field(..., description="当前对话窗口的唯一会话标识 (UUID)")

    # 7. 可选字段：大模型生成时的随机性。如果不传，默认就是 0.7
    temperature: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="模型回复的随机性")


# 8. 定义后端非流式对话时，返回给前端的标准 JSON 格式 (如果是流式打字机，前端直接接收字符串，就不走这个模型了)
class ChatResponse(BaseModel):
    # 比如我们查完向量库、大模型回答完，最终包装成这个格式返回
    answer: str = Field(..., description="大模型最终生成的回答文本")
    session_id: str = Field(..., description="原样返回会话ID，方便前端对齐")