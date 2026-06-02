# 文件路径: services/auth_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from models import User
from schemas import UserCreate


from security import get_password_hash, verify_password, create_access_token


# ==========================================
# 核心业务 1：处理用户注册
# ==========================================
async def register_user(db: AsyncSession, user_data: UserCreate):
    """
    处理注册逻辑
    1. 查数据库，看用户名是否被抢占了
    2. 把明文密码变成乱码
    3. 存入数据库
    """
    # 1. 查询用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="抱歉，该用户名已被注册")

    # 2. 调用你的截图代码：生成哈希密码
    hashed_pwd = get_password_hash(user_data.password)

    # 3. 填入 ORM 模型并存盘
    new_user = User(username=user_data.username, hashed_password=hashed_pwd)
    db.add(new_user)

    try:
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="数据库写入失败，请重试")


# ==========================================
# 核心业务 2：处理用户登录
# ==========================================
async def authenticate_user(db: AsyncSession, username: str, password: str):
    """
    处理登录逻辑
    1. 查数据库找人
    2. 核对密码
    3. 签发 Token 门票
    """
    # 1. 找人
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    # 2. 调用你的截图代码：核对密码 (找不到人或者密码错，统统报用户名或密码错误，防黑客探测)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 调用你的截图代码：签发 JWT 门票 (把用户名塞进 sub 字段)
    access_token = create_access_token(data={"sub": user.username})

    # 返回标准的 Token 格式
    return {"access_token": access_token, "token_type": "bearer"}