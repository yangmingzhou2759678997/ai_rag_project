from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import lifespan
from routers.auth import auth_router

# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有源，生产环境限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)

# 根路径
@app.get("/")
async def root():
    return {"message": "AI RAG System API", "version": "1.0.0"}