from slowapi import Limiter
from slowapi.util import get_remote_address

# 工业级限流器单例
# key_func=get_remote_address 意思是：系统会根据访问者的真实 IP 地址来进行限流盘点
limiter = Limiter(key_func=get_remote_address)