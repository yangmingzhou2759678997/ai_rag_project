from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from utils.rate_limiter import limiter
from routers.auth import router as auth_router
from database import lifespan
from utils.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)
from utils.logger import setup_logging, logger
from routers import auth, chat, knowledge
import models
# 1. 依然在最前端调用日志初始化，保证控制台有漂亮的彩色打印
setup_logging()

# 初始化 FastAPI 应用
app = FastAPI(
    title="基础 RAG 系统后端",
    version="1.0.0",
    lifespan=lifespan
)

# =================🚨 核心挂载 1：将限流器注册到 FastAPI 状态机=================
app.state.limiter = limiter

# =================🚨 核心挂载 2：组装系统终极防御矩阵 =================
# 1. 挂载限流报错 429
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# 2. 挂载 HTTP 主动报错 400, 401, 404 等
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
# 3. 挂载 Pydantic 数据校验报错 422
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# 4. 挂载终极未知崩溃 500
app.add_exception_handler(Exception, global_exception_handler)
# =================================================================

# 配置 CORS 跨域（纯标准件，看懂即可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# 🚨 核心挂载：将认证系统的路由接入主程序
# ======================
# 挂载路由
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
# ====================== 常规接口 ======================
@app.get("/")
async def root():
    logger.info("用户访问了根路由接口")
    return {"code": 200, "msg": "RAG Backend Running", "data": None}

@app.get("/api/v1/test/log")
async def test_log_endpoint():
    logger.info("正在执行第一步：解析用户权限...")
    logger.warning("知识库未命中！")
    logger.success("业务逻辑执行完毕！")
    return {"code": 200, "msg": "极简测试成功", "data": None}

