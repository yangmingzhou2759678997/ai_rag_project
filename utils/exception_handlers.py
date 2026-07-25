from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from openai import RateLimitError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_503_SERVICE_UNAVAILABLE

# 🚨 完美联动：导入我们之前写好的全链路日志！
from utils.logger import logger


# ======================
# 拦截上游大模型服务限流
# ======================
async def upstream_rate_limit_exception_handler(request: Request, exc: RateLimitError):
    logger.warning(" [上游模型限流] {} {} | 上游模型服务繁忙", request.method, request.url.path)
    return JSONResponse(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        content={"code": 503, "msg": "大模型服务繁忙，请稍后再试", "data": None}
    )


# ======================
# 1. 拦截 FastAPI 默认的 HTTP 异常 (如 404 找不到路由, 401 未登录)
# ======================
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    统一处理主动抛出的 HTTP 异常
    """
    logger.warning(
        f"️ [HTTP 异常拦截] {request.method} {request.url.path} | 状态码: {exc.status_code} | 原因: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": exc.detail,
            "data": None
        }
    )


# ======================
# 2. 拦截 Pydantic 数据校验异常 (如前端漏传了参数，或者密码长度不够 422)
# ======================
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    工业级优化：将 Pydantic 极其丑陋复杂的多层嵌套报错，展平翻译成人类能看懂的一句话
    例如将 [{"loc": ["body", "password"], "msg": "field required"}]
    展平为 -> "参数 [password] 校验失败: field required"
    """
    error_messages = []
    for error in exc.errors():
        # 获取出错的字段名（通常在 loc 列表的最后一个）
        field = str(error.get("loc")[-1]) if error.get("loc") else "未知字段"
        msg = error.get("msg")
        error_messages.append(f"参数 [{field}] 校验失败: {msg}")

    # 将多个参数错误用分号拼接起来
    flat_error_msg = " ; ".join(error_messages)

    logger.warning(f" [参数校验拦截] {request.method} {request.url.path} | 详情: {flat_error_msg}")

    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "msg": flat_error_msg,
            "data": None
        }
    )


# ======================
# 3. 终极兜底：拦截所有未预料的系统崩溃 (500 错误)
# ======================
async def global_exception_handler(request: Request, exc: Exception):
    """
    全场最核心的安全兜底防线
    作用：绝对不把系统真实报错信息（可能包含敏感数据库密码/API_KEY）暴露给外网前端！
    """
    # 1. 在后台日志里，用刺眼的红色打印完整的错误堆栈，方便排查
    logger.opt(exception=exc).error(" [系统致命崩溃] {} {} | 错误详情: {}", request.method, request.url.path, exc)

    # 2. 返回给前端的，永远只是一句温柔且安全的废话
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "msg": "服务器开小差了，请稍后再试",
            "data": None
        }
    )
