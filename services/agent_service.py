# 文件路径: services/agent_service.py
import time
import json
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services import memory_service
# 引入新增的 JSON Mode 重写接口
from clients.llm_client import get_llm_decision, get_llm_stream_response, rewrite_user_query_json_mode
from tools.rag_tool import search_knowledge_base
from tools.weather_tool import get_realtime_weather
from utils.logger import logger
from utils.background_tasks import log_request_production


# ==========================================
# 核心大脑：统筹处理一轮完整的 Agent 智能体生命周期
# ==========================================
async def process_chat_request(
        db: AsyncSession,
        user_id: int,
        session_id: str,
        query: str,
        background_tasks: BackgroundTasks
):
    try:
        # 1. 打卡上班记录
        start_time = time.time()
        logger.info(f"🧠 [Agent大脑] 收到对话 | 会话ID: {session_id} | 原始问题: {query}")

        # 2. 从数据库拉取历史滑动窗口记忆 (不含当前的新问题)
        history_messages = await memory_service.get_chat_history(db, session_id, window_size=10)

        # 3. 🚨【补漏核心：独立问题重写 Query Rewrite】
        # 拿着历史记录和最新残缺问题，让大模型用 JSON Mode 给出完整问题
        rewritten_query = await rewrite_user_query_json_mode(history_messages, query)

        # 4. 把原汁原味的用户问题存进数据库 (保证前端看到的聊天记录是真实的)
        await memory_service.save_message(db, user_id, session_id, "user", query)

        # 5. 组装真正喂给智能体做决策的 Messages 骨架 (使用重写后的问题！)
        final_messages = [
            {
                "role": "system",
                "content": "你是一个由国内顶尖AI工程师开发的智能助理。请用简洁、专业的中文回答问题。如果引用了工具提供的信息，请用专业语调进行整合归纳。"
            }
        ]
        final_messages.extend(history_messages)
        # 注意：这里传给大模型的是被重写过的清晰问题！
        final_messages.append({"role": "user", "content": rewritten_query})

        # 6. 非流式意图路由研判
        decision_message = await get_llm_decision(final_messages)

        # 7. Agent 工具执行链
        if decision_message.tool_calls:
            tool_call = decision_message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            logger.info(f"🎯 [Agent大脑] 触发工具: [{tool_name}] | 参数: {tool_args}")
            final_messages.append(decision_message)

            tool_output = ""
            if tool_name == "search_knowledge_base":
                # RAG 的查询也受益于重写！比如大模型提取出来的参数 query 就是重写后的完整句子
                extracted_query = tool_args.get("query", rewritten_query)
                tool_output = await search_knowledge_base(db, extracted_query)

            elif tool_name == "get_realtime_weather":
                extracted_city = tool_args.get("city_name", "苏州")
                tool_output = await get_realtime_weather(extracted_city)
            else:
                tool_output = "未知工具执行异常。"

            # 缝合工具结果回上下文
            final_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": tool_output
            })
            logger.info("🔗 [Agent大脑] 工具结果缝合完毕。")
        else:
            logger.info("💬 [Agent大脑] 无需工具，直接生成...")
            final_messages.append(decision_message)

        # 8. 终极流式打字机请求
        llm_stream = await get_llm_stream_response(final_messages)

        # 9. 闭包包装器与后台任务监控
        async def response_generator():
            full_answer = ""
            first_chunk_time = None

            try:
                async for chunk in llm_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                        full_answer += content
                        yield content
            finally:
                end_time = time.time()
                total_time = end_time - start_time
                ttfb = (first_chunk_time - start_time) if first_chunk_time else total_time
                status_code = 200 if full_answer else 500

                if full_answer:
                    await memory_service.save_message(db, user_id, session_id, "assistant", full_answer)

                background_tasks.add_task(
                    log_request_production,
                    method="POST",
                    path="/api/chat/completions",
                    status_code=status_code,
                    total_time=total_time,
                    ttfb=ttfb,
                    model=settings.chat_model,
                    user_id=str(user_id),
                    error_message=None if full_answer else "流中途断开"
                )

        return response_generator()

    except Exception as e:
        logger.error(f"❌ [Agent大脑] 智能体中枢崩溃: {e}")
        raise e