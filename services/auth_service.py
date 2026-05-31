# 文件路径: services/auth_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from models import User
from schemas import UserCreate
from security import get_password_hash, verify_password, create_access_token


async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    工业级注册逻辑：检查重名 -> 密码加密 -> 存入数据库
    """
    # 1. 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_in.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册"
        )

    # 2. 将明文密码转为 bcrypt 乱码
    hashed_password = get_password_hash(user_in.password)

    # 3. 创建数据库 ORM 实例并保存
    new_user = User(
        username=user_in.username,
        hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


async def authenticate_user(db: AsyncSession, username: str, password: str):
    """
    工业级登录逻辑：查询用户 -> 比对密码乱码 -> 签发 JWT 门票
    """
    # 1. 去数据库找这个人
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    # 2. 如果人不存在，或者密码比对失败，统统返回“账号或密码错误”（防黑客探测）
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 校验通过，用他的用户 ID 签发专属 JWT Token
    access_token = create_access_token(data={"sub": str(user.id)})

    # 返回标准的 Token 格式字典
    return {"access_token": access_token, "token_type": "bearer"}