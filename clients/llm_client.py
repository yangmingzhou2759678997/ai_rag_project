# 覆盖替换文件路径: clients/llm_client.py
from openai import AsyncOpenAI, pydantic_function_tool
from openai.types.chat import ChatCompletionMessage
from pydantic import BaseModel, Field
from config import settings
from utils.logger import logger
import json
from threading import Lock


# 创建单例
class OpenAIClient:
    _instance: AsyncOpenAI | None = None
    _lock: Lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    try:
                        cls._instance = AsyncOpenAI(
                            api_key=settings.openai_api_key,
                            base_url=settings.openai_base_url
                        )
                        logger.info(" 成功建立大模型云端异步连接客户端！")
                    except Exception as e:
                        logger.error(f" 大模型客户端初始化失败: {e}")
                        raise e
        return cls._instance


llm_client = OpenAIClient()


# ==========================================
# 第二部分：定义智能体的工具清单
# ==========================================
class RAGToolArgs(BaseModel):
    query: str = Field(..., description="提取出的需要进入外部数据库进行匹配的具体搜索词或完整问句。")


class WeatherToolArgs(BaseModel):
    city_name: str = Field(..., description="需要查询天气的城市名称。")


rag_tool_schema = pydantic_function_tool(
    model=RAGToolArgs,
    name="search_knowledge_base",
    description=(
        "【企业通用数据检索器】这是你的核心外部记忆库。只要用户的提问超出了日常寒暄的范畴，"
        "涉及到任何客观事实、机构规章、专业知识、业务数据等需要严谨依据的问题时，你绝不能使用自己预训练的知识去回答。"
        "【必须且只能】静默调用此工具！绝对禁止试图用你自己的预训练知识去盲猜，也绝对禁止在调用前输出'好的，让我为您查询'等过渡性废话。"
    )
)

weather_tool_schema = pydantic_function_tool(
    model=WeatherToolArgs,
    name="get_realtime_weather",
    description="用于查询指定城市的实时天气数据。"
)
agent_tools = [rag_tool_schema, weather_tool_schema]


# ==========================================
#  3：强力剥离 JSON Mode 的 Markdown 污染
# ==========================================
async def rewrite_user_query_json_mode(history_messages: list, current_query: str) -> str:
    system_prompt = (
        "你是一个极其精准的语义重写专家。你的任务是结合用户的历史聊天记录，将用户的最新问题重写为一个独立、完整、不包含代词(如'他'、'这个')的陈述句提问。\n"
        "重写只负责补全省略的实体、文件、阶段、日期、章节和代词，不得添加其他问题。\n"
        "最新问题实际询问的属性、动作和目标拥有最高优先级，历史消息只用于补全上下文。\n"
        "禁止因为历史问题询问配置、时间、位置、人员等，就机械地把同一个询问属性带入最新问题。\n"
        "当最新问题使用“那下一天”“同名第五天”“后一个阶段”等表达时，应结合历史补全目标，但不得改变最新问题原本的询问意图。\n"
        "当最新问题只包含“那……呢”“后一个呢”“下一阶段呢”等目标切换表达，且没有明确重复上一轮询问的属性、动作或目标时，只补全新的目标，并使用“该目标的相关规定是什么”或“该目标具体如何处理”等中性问法；禁止自动继承上一轮的“什么配置、多少时间、放在哪里、由谁负责”等询问属性。\n"
        "例如上一轮询问某阶段的配置、最新问题仅切换到另一个阶段时，应重写为另一个阶段的相关规定是什么，而不是继续询问配置。\n"
        "必须保留用户明确给出的文件类型、文件名、阶段、天数、章节和顺序限制。\n"
        "如果最新问题已经完整，请保持原意，不扩展出额外问题。\n"
        "极其重要：你必须且只能返回一个合法的 JSON 对象，格式必须完全遵守：{\"rewritten_query\": \"重写后的完整问题\"}这种样式。"
    )
    rewrite_messages = [{"role": "system", "content": system_prompt}]
    rewrite_messages.extend(history_messages)
    rewrite_messages.append({"role": "user", "content": f"最新问题是：{current_query}"})

    try:
        response = await llm_client.chat.completions.create(
            model=settings.chat_model,
            messages=rewrite_messages,
            temperature=0,
            response_format={"type": "json_object"}
        )
        json_str = response.choices[0].message.content.strip()
        #  防止 Markdown 标签
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()

        result_dict = json.loads(json_str)
        rewritten_query = result_dict.get("rewritten_query", current_query)

        logger.info(f" [LLM 重写层] 重写成功: '{current_query}' -> '{rewritten_query}'")
        return rewritten_query

    except Exception as e:
        logger.error(f" [LLM 重写层] 问题重写失败，退回到原始问题兜底: {e}")
        return current_query


async def get_llm_decision(messages: list) -> ChatCompletionMessage:
    try:
        response = await llm_client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=settings.openai_temperature,
            stream=False,
            tools=agent_tools,
            tool_choice="auto"  # 先让 LLM 自主判断，后续兜底
        )
        decision_msg = response.choices[0].message
        # 核心兜底：如果未触发任何工具，强制调用 search_knowledge_base
        if not decision_msg.tool_calls:
            logger.warning(" [LLM 决策层] 未触发工具，强制兜底调用 search_knowledge_base")
            # 构造强制调用工具的消息
            decision_msg.tool_calls = [
                {
                    "id": "forced_tool_call_001",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": json.dumps({"query": messages[-1]["content"]})  # 取最新用户问题作为查询词
                    },
                    "type": "function"
                }
            ]
        return decision_msg
    except Exception as e:
        logger.error(f" [LLM 决策层] 意图研判发生致命错误: {e}")
        raise e


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
        logger.error(f" [LLM 生成层] 流式接口响应失败: {e}")
        raise e
