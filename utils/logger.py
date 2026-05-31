# utils/logger.py
import os
import sys
import logging
from pathlib import Path
from contextvars import ContextVar

# 明确依赖：pip install loguru pydantic-settings
from loguru import logger

# ====================== 全局配置 ======================
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 全链路请求ID上下文变量（必须导出，供FastAPI中间件注入ID）
request_id: ContextVar[str] = ContextVar("request_id", default="-")

# 从环境变量读取日志级别，默认 INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ====================== 动态上下文补丁 (核心解锁) ======================
def _dynamic_request_id_patcher(record):
    """
    100分工业级解法：动态补丁机制
    每次日志触发的瞬间，动态从当前异步协程上下文中提取真正的 Request ID
    彻底解决模块顶级导入导致的‘初始值死锁’Bug
    """
    record["extra"]["request_id"] = request_id.get()

# ====================== 日志格式定义 ======================
# 控制台彩色格式
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<magenta>{extra[request_id]}</magenta> | "
    "<lvl>{level: <8}</lvl> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<lvl>{message}</lvl>"
)

# 文件纯文本格式
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{extra[request_id]} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)

# ====================== 标准库日志纯异步拦截器 ======================
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

# ====================== 日志初始化函数 ======================
def setup_logging() -> None:
    """
    初始化全局日志系统。在 main.py 的 lifespan 启动时最前端调用。
    """
    # 清除 loguru 默认配置
    logger.remove()

    # 💡 核心亮点：全局配置动态补丁，把解耦做到极致
    logger.configure(patcher=_dynamic_request_id_patcher)

    # 1. 控制台输出
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format=CONSOLE_FORMAT,
        colorize=True,
        enqueue=True,    # 开启线程安全队列，纯异步不阻塞主线程
        backtrace=True,
        diagnose=(LOG_LEVEL == "DEBUG"), # 🔒 只有开发环境DEBUG才开启diagnose，生产环境关闭，防机密泄露
    )

    # 2. INFO级别日志文件
    logger.add(
        LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        level="INFO",
        format=FILE_FORMAT,
        rotation="midnight",
        retention="30 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,  # 🔒 线上日志文件绝对禁止开启 diagnose，严防 API Key 和核心数据泄露
    )

    # 3. ERROR级别日志文件
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=FILE_FORMAT,
        rotation="midnight",
        retention="90 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,  # 🔒 绝对关闭，保障数据安全合规
    )

    # 4. 优化：标准库拦截级别对齐系统级别，不捕获过多的底层的垃圾事件
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    # 5. 降低高频第三方库的刷屏噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

# ====================== 完美的导出 ======================
# 💡 2026 去框架化标准：不再需要 get_logger 函数，在其他文件直接 from utils.logger import logger 即可
__all__ = ["setup_logging", "logger", "request_id"]