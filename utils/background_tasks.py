from utils.logger import logger


async def log_request_production(
        method: str,
        path: str,
        status_code: int,
        total_time: float,
        ttfb: float,
        model: str,
        user_id: str,
        error_message: str = None
):
    """
    工业级大模型流式接口性能监控后台任务

    作用：在 SSE 流完全关闭后，异步记录首字延迟(TTFB)、总耗时和模型信息，
    绝不阻塞主线程，完全契合高并发生产环境。
    """
    try:
        # 如果是 200 成功响应
        if status_code == 200:
            logger.success(
                f"📊 [流式响应大捷] {method} {path} | "
                f"用户:{user_id} | 模型:{model} | "
                f"首字延迟(TTFB): {ttfb:.3f}秒 | 总耗时: {total_time:.3f}秒"
            )
        # 如果中途崩溃报错
        else:
            logger.error(
                f"❌ [流式响应崩溃] {method} {path} | "
                f"状态码:{status_code} | 报错原因:{error_message} | "
                f"耗时:{total_time:.3f}秒"
            )

    except Exception as e:
        logger.error(f"⚠️ 后台日志记录任务自身发生异常: {e}")