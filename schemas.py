from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


# ==========================================
# 第一部分：认证与用户模块 (Auth Schemas)
# ==========================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="明文密码")


class UserResponse(BaseModel):
    id: int
    username: str

    # 🚨 核心修复 1：纯正的 Pydantic V2 语法，适配 ORM
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ==========================================
# 第二部分：AI 聊天模块 (Chat Schemas)
# ==========================================
class ChatRequest(BaseModel):
    query: str = Field(..., description="用户发出的提问内容")
    session_id: str = Field(..., description="当前对话窗口的唯一会话标识 (UUID)")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="模型回复的随机性")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="大模型最终生成的回答文本")
    session_id: str = Field(..., description="原样返回会话ID，方便前端对齐")


# ==========================================
# 第三部分：智能体工具参数模型 (Agent Tool Schemas)
# ==========================================
class RAGToolArgs(BaseModel):
    query: str = Field(..., description="需要去知识库检索的具体问题。例如：'带薪年假有几天？'")


class WeatherToolArgs(BaseModel):
    city_name: str = Field(..., description="需要查询天气的具体城市名称，例如：'苏州'、'北京'")