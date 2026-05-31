from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import UserResponse, UserCreate, Token
from services.auth_service import register_user, authenticate_user
from utils.logger import logger

# 创建认证专属路由器
router = APIRouter(prefix="/api/v1/auth", tags=["认证系统"])

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    用户注册接口
    """
    logger.info(f"👤 收到新用户注册请求: {user_in.username}")
    new_user = await register_user(db, user_in)
    logger.success(f"✅ 用户 {new_user.username} 注册成功！")
    return new_user

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    用户登录接口 (兼容 OAuth2 标准，支持 Swagger UI 一键 Auth)
    """
    logger.info(f"🔑 用户尝试登录: {form_data.username}")
    token_dict = await authenticate_user(db, form_data.username, form_data.password)
    logger.success(f"🔓 用户 {form_data.username} 登录成功，已签发 JWT Token！")
    return token_dict