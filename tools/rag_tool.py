# 文件路径: tools/rag_tool.py
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Document
from clients.llm_client import llm_client
from utils.logger import logger
from config import settings


async def get_text_embedding(text: str) -> list[float]:
    """调用云端大模型，将文本转换为 1024 维向量"""
    try:
        response = await llm_client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"❌ 向量化转换失败: {e}")
        raise e


async def search_knowledge_base(db: AsyncSession, query: str) -> str:
    """
    工业级 RAG 检索工具：Query -> Vector Search (粗排) -> Rerank (精排) -> 降级兜底
    """
    logger.info(f"🔎 [RAG工具] 开始检索内部知识库: '{query}'")
    try:
        # ==========================================
        # 1. 向量化问题
        # ==========================================
        query_vector = await get_text_embedding(query)

        # ==========================================
        # 2. 粗排阶段 (Recall Top K)
        # ==========================================
        stmt = (
            select(Document.content)
            .order_by(Document.embedding.cosine_distance(query_vector))
            .limit(settings.recall_top_k)  # 默认召回 10 条
        )
        result = await db.execute(stmt)
        recall_chunks = result.scalars().all()

        if not recall_chunks:
            return "未找到相关内部资料。"

        # ==========================================
        # 3. 精排阶段 (Rerank) 与 服务降级防御矩阵
        # ==========================================
        logger.info(f"⚖️ [RAG工具] 粗排召回 {len(recall_chunks)} 条，开始重排...")

        try:
            # 🚨 优化 1：使用 timeout=4.0 实现 Fail-Fast (快速失败)，绝不拖死主线程
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": settings.reranker_model,
                    "query": query,
                    "texts": recall_chunks,
                    "return_documents": True,
                    "top_n": settings.rerank_top_k
                }
                headers = {
                    "Authorization": f"Bearer {settings.reranker_api_key}",
                    "Content-Type": "application/json"
                }
                res = await client.post(
                    settings.reranker_api_url,
                    json=payload,
                    headers=headers,
                    timeout=4.0
                )
                res.raise_for_status()
                rerank_data = res.json()

            # 组装最终结果，过滤低分数据
            final_chunks = []
            for item in rerank_data.get("results", []):
                if item["relevance_score"] >= settings.rerank_score_threshold:
                    final_chunks.append(item["document"]["text"])

            if not final_chunks:
                return "检索到的资料相关性过低，不予参考。"

            logger.info("✅ [RAG工具] 精排完成，资料已就绪。")
            return "\n\n".join(final_chunks)

        # 🚨 优化 2：捕获超时与网络异常，触发大厂级【服务降级】
        except httpx.TimeoutException:
            logger.warning("⚠️ [RAG防御矩阵] Reranker 接口响应超时！已触发【服务降级】，直接返回粗排 Top-3 结果。")
            return "\n\n".join(recall_chunks[:3])

        except Exception as e:
            logger.warning(f"⚠️ [RAG防御矩阵] Reranker 发生异常: {e}。已触发【服务降级】，直接返回粗排 Top-3 结果。")
            return "\n\n".join(recall_chunks[:3])

    except Exception as e:
        logger.error(f"❌ [RAG工具] 检索知识库发生严重级崩溃: {e}")
        return "内部知识库检索系统发生异常，暂无法提供资料。"