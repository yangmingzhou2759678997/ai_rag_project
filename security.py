import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

# 导入全局配置，用于读取密钥
from config import settings
from utils.logger import logger


def get_password_hash(password: str) -> str:
    """
    【动作 1：注册时用】将用户的明文密码加密成无法破解的乱码（Hash）
    """
    # 1. 将字符串转为字节
    pwd_bytes = password.encode('utf-8')
    # 2. 生成随机盐值（加盐是为了防止黑客用彩虹表反向破解）
    salt = bcrypt.gensalt()
    # 3. 进行哈希运算
    hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)

    # 返回解码后的字符串存入数据库
    return hashed_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    【动作 2：登录时用】校验用户输入的密码是否与数据库里的乱码匹配
    """
    try:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        # bcrypt.checkpw 会自动处理“盐”的匹配，非常安全
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"密码校验过程中发生异常: {e}")
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    【动作 3：签发门票】验证密码成功后，给用户颁发一张带有有效期的 JWT 门票（Token）
    """
    to_encode = data.copy()

    # 确定过期时间 (如果没有特别指定，就用 config 里的默认时间)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 把过期时间戳塞进字典里
    to_encode.update({"exp": expire})

    # 核心魔法：使用系统隐藏的 SECRET_KEY 和 HS256 算法生成乱码字符串 Token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt