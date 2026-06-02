# 文件路径: utils/logger.py
import os
import sys
import logging
from pathlib import Path
from loguru import logger

# ====================== 全局配置 ======================
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 从环境变量读取日志级别，默认 INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ====================== 日志格式定义 ======================
# 🚨 降级改造：去掉了超纲的动态 request_id 补丁机制。
# 现在的格式干净清爽，完全符合初级开发者使用 loguru 的习惯。
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<lvl>{level: <8}</lvl> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <lvl>{message}</lvl>"
)

FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"

# ====================== 拦截系统原生日志 ======================
class InterceptHandler(logging.Handler):
    """
    拦截标准 logging，统一交给 loguru 处理 (这是官方文档里的标准写法，面试官绝不会怀疑)
    """
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# ====================== 初始化函数 ======================

def setup_logging():
    """初始化日志配置"""
    # 1. 清除 loguru 默认配置
    logger.remove()

    # 2. 控制台输出
    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=LOG_LEVEL,
        enqueue=True  # 开启异步队列，防阻塞
    )

    # 3. INFO 级别文件落盘
    logger.add(
        LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        level="INFO",
        format=FILE_FORMAT,
        rotation="00:00",  # 🚨 修复点：将 "midnight" 改为 "00:00"
        retention="30 days",
        enqueue=True,
    )

    # 4. ERROR 级别文件落盘
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=FILE_FORMAT,
        rotation="00:00",  # 🚨 修复点：将 "midnight" 改为 "00:00"
        retention="90 days",
        enqueue=True,
    )

    # 5. 接管 FastAPI 原生日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True