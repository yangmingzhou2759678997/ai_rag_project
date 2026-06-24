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
        logger.error(f" 向量化转换失败: {e}")
        raise e


async def search_knowledge_base(db: AsyncSession, query: str) -> str:
    """
    工业级 RAG 检索工具：Query -> Vector Search (粗排) -> Rerank (精排) -> 弹性降级兜底
    """
    logger.info(f" [RAG工具] 开始检索内部知识库: '{query}'")
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
        # 3. 精排阶段 (Rerank) 与 弹性兜底机制
        # ==========================================
        logger.info(f" [RAG工具] 粗排召回 {len(recall_chunks)} 条，开始重排...")

        try:
            # 护盾 1：防静默截断，截取每个文本块前350个字符
            safe_chunks = [chunk[:350] for chunk in recall_chunks]
            safe_query = query[:100]

            async with httpx.AsyncClient() as client:
                payload = {
                    "model": settings.reranker_model,
                    "query": safe_query,
                    "texts": safe_chunks,
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

            # 解析结果
            results = rerank_data.get("results", [])
            final_chunks = []

            # 按照设定的 rerank_score_threshold 严格过滤
            for item in results:
                if item["relevance_score"] >= settings.rerank_score_threshold:
                    document = item.get("document", {})
                    text = document.get("text", "")
                    if text:
                        final_chunks.append(text)

            # 弹性兜底机制
            # 如果所有的文本都被分数阈值挡下了，但 API 确实返回了排序后的结果
            if not final_chunks and results:
                highest_score = results[0]["relevance_score"]
                logger.warning(
                    f" Reranker 过滤太严苛 (最高分仅 {highest_score:.3f}，低于阈值)。触发弹性兜底，强制将排名第一的文本喂给大模型！")
                # 强行把第一名塞进去，让大模型自己去做阅读理解判断对错！
                final_chunks.append(results[0]["document"]["text"])

            if not final_chunks:
                return "检索到的资料相关性过低，不予参考。"

            logger.info(f" [RAG工具] 精排完成，最终采纳了 {len(final_chunks)} 条资料。")
            return "\n\n".join(final_chunks)

        except httpx.TimeoutException:
            logger.warning(" [RAG防御矩阵] Reranker 超时！降级返回粗排 Top-3。")
            return "\n\n".join(recall_chunks[:3])

        except Exception as e:
            logger.warning(f"️ [RAG防御矩阵] Reranker 发生异常: {e}。降级返回粗排 Top-3。")
            return "\n\n".join(recall_chunks[:3])

    except Exception as e:
        logger.error(f" [RAG工具] 检索发生严重级崩溃: {e}")
        return "内部知识库检索系统发生异常，暂无法提供资料。"