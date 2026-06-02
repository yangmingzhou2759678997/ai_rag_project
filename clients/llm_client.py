# 文件路径: clients/llm_client.py
from openai import AsyncOpenAI
from config import settings
from utils.logger import logger
import json

# ==========================================
# 第一部分：初始化大模型客户端 (全局单例)
# ==========================================
try:
    llm_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )
    logger.info("✅ 成功建立大模型云端异步连接客户端！")
except Exception as e:
    logger.error(f"❌ 大模型客户端初始化失败: {e}")
    raise e

# ==========================================
# 第二部分：定义智能体的“武器清单” (Function Calling Schema)
# ==========================================
rag_tool_schema = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "当用户询问关于公司制度、设备维修、内部规章、财务报销、网络指南或任何需要查阅内部知识库的问题时，必须调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要去知识库检索的具体问题。例如：'带薪年假有几天？'"
                }
            },
            "required": ["query"]
        }
    }
}

weather_tool_schema = {
    "type": "function",
    "function": {
        "name": "get_realtime_weather",
        "description": "当用户询问某个城市今天、实时、现在的天气、温度或气候情况时，必须调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "city_name": {
                    "type": "string",
                    "description": "需要查询天气的具体城市名称，例如：'苏州'、'北京'"
                }
            },
            "required": ["city_name"]
        }
    }
}

agent_tools = [rag_tool_schema, weather_tool_schema]


# ==========================================
# 第三部分：解耦接口 A - 【补漏新增】独立问题重写 (强制 JSON Mode)
# ==========================================
async def rewrite_user_query_json_mode(history_messages: list, current_query: str) -> str:
    """
    问题重写引擎 (JSON Mode)
    作用：解决多轮对话中的“代词指代不明”问题。强制大模型返回 JSON，确保 100% 稳定解析。
    """
    logger.info("✍️ [LLM 重写层] 正在结合历史记忆，重写用户问题...")

    # 1. 构造极其严苛的重写系统提示词
    system_prompt = (
        "你是一个极其精准的语义重写专家。你的任务是结合用户的聊天记录，将用户的最新问题重写为一个独立、完整、不包含代词(如'他'、'这个')的陈述句提问。\n"
        "如果最新问题已经是完整的，请保持原意返回。\n"
        "🚨 极其重要：你必须且只能返回一个合法的 JSON 对象，格式必须完全遵守：{\"rewritten_query\": \"重写后的完整问题\"}"
    )

    # 2. 组装专门用于重写的消息体
    rewrite_messages = [{"role": "system", "content": system_prompt}]
    rewrite_messages.extend(history_messages)
    rewrite_messages.append({"role": "user", "content": f"最新问题是：{current_query}"})

    try:
        response = await llm_client.chat.completions.create(
            model=settings.chat_model,
            messages=rewrite_messages,
            temperature=0.1,  # 重写任务必须极度严谨，温度降到最低
            # 🚨 解决暗伤二的终极绝杀：开启 OpenAI 官方 JSON Mode
            response_format={"type": "json_object"}
        )

        # 3. 解析 JSON 字符串拿到重写后的问题
        json_str = response.choices[0].message.content
        result_dict = json.loads(json_str)
        rewritten_query = result_dict.get("rewritten_query", current_query)

        logger.info(f"✅ [LLM 重写层] 重写成功: '{current_query}' -> '{rewritten_query}'")
        return rewritten_query

    except Exception as e:
        logger.error(f"❌ [LLM 重写层] 问题重写失败，退回到原始问题兜底: {e}")
        # 如果重写意外失败，不阻断流程，直接用原问题继续往下走
        return current_query


# ==========================================
# 第四部分：解耦接口 B - 非流式工具路由决策
# ==========================================
async def get_llm_decision(messages: list):
    try:
        response = await llm_client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=settings.openai_temperature,
            stream=False,
            tools=agent_tools,
            tool_choice="auto"
        )
        return response.choices[0].message
    except Exception as e:
        logger.error(f"❌ [LLM 决策层] 意图研判发生致命错误: {e}")
        raise e


# ==========================================
# 第五部分：解耦接口 C - 纯粹的流式打字机输出
# ==========================================
async def get_llm_stream_response(messages: list):
    try:
        response = await llm_client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=settings.openai_temperature,
            stream=True
        )
        return response
    except Exception as e:
        logger.error(f"❌ [LLM 生成层] 流式接口响应失败: {e}")
        raise e