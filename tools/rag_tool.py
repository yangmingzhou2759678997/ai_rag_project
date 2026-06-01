# 文件路径: tools/rag_tool.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Document
from clients.llm_client import llm_client  # 复用我们已经写好的云端单例连接器
from utils.logger import logger
from config import settings


# ==========================================
# 核心前置动作：将人类语言变成“向量数字” (Embedding)
# ==========================================
async def get_text_embedding(text: str) -> list[float]:
    """
    文本向量化工具
    作用：把一句话（比如"苏州天气"），变成一个包含 1024 个浮点数的数组。
    """
    try:
        # 1. 调用大模型厂商的 Embedding 接口
        # 这里使用的是 BAAI/bge-m3，国内目前开源做 RAG 最顶尖的向量模型之一，维度是 1024
        response = await llm_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,  # 建议后续替换为 settings.EMBEDDING_MODEL
            input=text
        )

        # 2. 从 OpenAI 兼容格式的返回值中，精准提取出那个数组
        embedding_vector = response.data[0].embedding
        return embedding_vector

    except Exception as e:
        logger.error(f"❌ 文本向量化(Embedding)转换失败: {e}")
        raise e


# ==========================================
# 核心主战技能：检索知识库 (Agentic RAG Tool)
# ==========================================
async def search_knowledge_base(db: AsyncSession, query: str, top_k: int = 3) -> str:
    """
    知识库核心检索技能
    作用：被 agent_service 调用。拿着用户的问题，去 PGVector 数据库里把答案捞出来。

    :param db: 数据库连接会话
    :param query: 用户最新的提问，比如 "公司的请假制度是什么？"
    :param top_k: 捞取最相似的前 N 块内容，默认捞 3 块
    :return: 拼装好的参考资料字符串
    """
    logger.info(f"🔎 [RAG Tool] 开始检索知识库，提问: '{query}'")

    try:
        # ---------------------------------------------------------
        # 第一步：用户提问向量化 (Query Embedding)
        # 数据库里的文档已经是向量了，要想做对比，必须把用户的问题也变成同等维度的向量。
        # ---------------------------------------------------------
        query_vector = await get_text_embedding(query)

        # ---------------------------------------------------------
        # 第二步：向量相似度比对与查询 (Vector Search)
        # 这是 PGVector 的绝活！计算问题向量与数据库中每个文档向量的“余弦距离”。
        # ---------------------------------------------------------
        stmt = (
            select(Document.content)
            # cosine_distance 是余弦距离。距离越小，代表语义越相似。所以我们用升序 (默认) 排列。
            .order_by(Document.embedding.cosine_distance(query_vector))
            # 只拿排名最靠前（距离最小、最相似）的前 top_k 个文本块
            .limit(top_k)
        )

        # 抛给数据库去执行复杂的数学运算
        result = await db.execute(stmt)

        # 提取出真实的文本内容列表，比如: ["请假制度第一条...", "请假制度第二条..."]
        similar_chunks = result.scalars().all()

        # ---------------------------------------------------------
        # 第三步：结果组装与防空兜底
        # ---------------------------------------------------------
        if not similar_chunks:
            logger.warning("⚠️ [RAG Tool] 知识库中未检索到任何相关内容。")
            return "未找到相关内部资料。"

        # 将多个文本块用换行符拼接成一个巨大的“参考文档”字符串
        rag_context = "\n\n---\n\n".join(similar_chunks)

        logger.info(f"✅ [RAG Tool] 成功检索到 {len(similar_chunks)} 块高度相关的资料。")
        return rag_context

    except Exception as e:
        logger.error(f"❌ [RAG Tool] 知识库检索流程全面崩溃: {e}")
        # RAG 查阅失败不应该导致聊天中断，所以我们捕获异常，返回一个友好的错误提示给大脑
        return "检索内部知识库时发生错误，请以您的通用知识进行回答。"