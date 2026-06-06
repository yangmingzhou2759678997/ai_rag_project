# 覆盖替换文件路径: services/agent_service.py
import time
import json
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services import memory_service
from clients.llm_client import get_llm_decision, get_llm_stream_response, rewrite_user_query_json_mode
from tools.rag_tool import search_knowledge_base
from tools.weather_tool import get_realtime_weather
from utils.logger import logger
from utils.background_tasks import log_request_production
from database import AsyncSessionLocal


async def process_chat_request(
        db: AsyncSession,
        user_id: int,
        session_id: str,
        query: str,
        background_tasks: BackgroundTasks
):
    try:
        start_time = time.time()
        logger.info(f"🧠 [Agent大脑] 收到对话 | 会话ID: {session_id} | 原始问题: {query}")

        history_messages = await memory_service.get_chat_history(db, session_id, window_size=10)
        rewritten_query = await rewrite_user_query_json_mode(history_messages, query)

        await memory_service.save_message(db, user_id, session_id, "user", query)

        final_messages = [
            {
                "role": "system",
                "content": (
                    "你是企业智能助理，你的核心职责是基于企业内部知识库回答问题，严格遵守以下铁律：\n"
                    "【强制规则 1】：无论用户问题是什么，除了纯日常寒暄（仅包含：你好、谢谢、再见、早上好、下午好、晚上好），"
                    "必须优先调用 search_knowledge_base 工具，禁止直接用自身知识回答任何问题！\n"
                    "【强制规则 2】：调用工具时，禁止输出任何过渡性话语（如“让我查询一下”“稍等”），直接静默调用工具！\n"
                    "【强制规则 3】：工具返回结果为空/无相关信息时，仅能回复：“抱歉，我在公司知识库中未找到相关信息”，禁止补充任何额外内容！\n"
                    "【强制规则 4】：仅当用户明确提问“天气”相关问题时，才可调用 get_realtime_weather 工具，其他场景禁止调用！\n"
                    "【强制规则 5】：工具调用完成后，仅能基于工具返回的内容整理回答，禁止添加任何自身预训练的知识、推测、解释！\n"
                    "【惩罚机制】：违反以上任意规则，立即终止回答！"
                )
            }
        ]
        final_messages.extend(history_messages)
        final_messages.append({"role": "user", "content": rewritten_query})

        decision_message = await get_llm_decision(final_messages)

        # 🚨 统一工具调用格式：无论来自大模型还是手动创建，全部转为标准字典
        tool_calls = []

        # 第一步：处理大模型返回的工具调用
        if decision_message.tool_calls:
            for tc in decision_message.tool_calls:
                # 兼容OpenAI原生对象和字典格式
                if hasattr(tc, "__dict__"):
                    tc_dict = tc.__dict__.copy()
                    if hasattr(tc_dict["function"], "__dict__"):
                        tc_dict["function"] = tc_dict["function"].__dict__.copy()
                    tool_calls.append(tc_dict)
                else:
                    tool_calls.append(tc)
            logger.info(f"🎯 [Agent大脑] 大模型触发工具调用，共 {len(tool_calls)} 个")

        # 第二步：代码级强制兜底（如果大模型没有调用工具且不是寒暄）
        if not tool_calls:
            greetings = {"你好", "您好", "嗨", "hello", "hi", "谢谢", "感谢", "再见", "拜拜", "早上好", "下午好",
                         "晚上好"}
            is_greeting = rewritten_query.strip().lower() in greetings

            if not is_greeting:
                logger.warning("⚠️ [Agent大脑] 大模型未触发RAG工具，触发代码级强制兜底！")
                # 手动构造标准字典格式的工具调用（100%兼容所有情况）
                tool_calls = [
                    {
                        "id": f"forced_{int(time.time())}",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": json.dumps({"query": rewritten_query})
                        }
                    }
                ]
                logger.info(f"🎯 [Agent大脑] 强制触发工具调用，共 {len(tool_calls)} 个")
            else:
                logger.info("💬 [Agent大脑] 大模型判断为日常寒暄，直接回复...")

        # 第三步：处理所有工具调用（纯字典操作，零类型问题）
        if tool_calls:
            # 构造符合OpenAI规范的assistant消息
            assistant_msg = {
                "role": "assistant",
                "content": decision_message.content or "",
                "tool_calls": tool_calls
            }
            final_messages.append(assistant_msg)

            # 循环执行所有工具
            for tc in tool_calls:
                tool_id = tc["id"]
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"]["arguments"])

                logger.info(f"  -> 执行工具: [{tool_name}] | 参数: {tool_args}")
                tool_output = ""

                if tool_name == "search_knowledge_base":
                    extracted_query = tool_args.get("query", rewritten_query)
                    tool_output = await search_knowledge_base(db, extracted_query)
                elif tool_name == "get_realtime_weather":
                    extracted_city = tool_args.get("city_name", "苏州")
                    tool_output = await get_realtime_weather(extracted_city)
                else:
                    tool_output = "未知工具执行异常。"

                # 添加工具结果（完全符合OpenAI v1.30+规范，无多余字段）
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": tool_output
                })

            logger.info("🔗 [Agent大脑] 所有工具结果缝合完毕。")

        # 第四步：流式生成最终回答
        llm_stream = await get_llm_stream_response(final_messages)

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
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                end_time = time.time()
                total_time = end_time - start_time
                ttfb = (first_chunk_time - start_time) if first_chunk_time else total_time
                status_code = 200 if full_answer else 500

                if full_answer:
                    async with AsyncSessionLocal() as fresh_db:
                        await memory_service.save_message(fresh_db, user_id, session_id, "assistant", full_answer)

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
        logger.error(f"❌ [Agent大脑] 智能体中枢崩溃: {e}", exc_info=True)
        raise e