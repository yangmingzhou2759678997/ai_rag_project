from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. 依然在最前端调用日志初始化，保证控制台有漂亮的彩色打印
from utils.logger import setup_logging, logger
setup_logging()

from routers.auth import router as auth_router

# 初始化 FastAPI 应用
from database import lifespan
app = FastAPI(
    title="基础 RAG 系统后端",
    version="1.0.0",
    lifespan=lifespan
)

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
app.include_router(auth_router)

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