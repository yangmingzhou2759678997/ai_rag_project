# 文件路径: routers/auth.py
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

# 导入你的基建模块
from database import get_db
from schemas import UserCreate, UserResponse, Token
from services.auth_service import register_user, authenticate_user
from utils.logger import logger

# 创建路由前缀 /api/auth
router = APIRouter(prefix="/api/auth", tags=["认证与安全模块"])

# ==========================================
# 对外接口 1：注册接口
# ==========================================
@router.post("/register", response_model=UserResponse, summary="新用户注册")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    接收前端传来的 {"username": "xx", "password": "xx"}，交由 service 处理
    """
    logger.info(f" 收到注册请求: {user_data.username}")
    # 调大脑
    new_user = await register_user(db, user_data)
    return new_user

# ==========================================
# 对外接口 2：登录接口
# ==========================================
@router.post("/login", response_model=Token, summary="用户登录换取 Token")
async def login(
    # 注意：FastAPI 官方规范要求登录接口接收 Form 表单数据 (OAuth2PasswordRequestForm)，而不是普通 JSON
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    前端提交用户名和密码，后端核对成功后颁发 JWT 字符串
    """
    logger.info(f" 收到登录请求: {form_data.username}")
    # 调大脑
    token_dict = await authenticate_user(db, form_data.username, form_data.password)
    return token_dict