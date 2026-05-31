from pydantic import BaseModel, Field

# 1. 注册时接收的数据格式
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="明文密码")

# 2. 返回给前端的用户信息格式（注意：绝对不能包含密码！）
class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True  # 允许从 SQLAlchemy ORM 模型自动转换

# 3. 登录成功后返回的 JWT Token 格式
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"