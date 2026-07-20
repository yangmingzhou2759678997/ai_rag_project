# 文件路径: tools/rag_tool.py
import os
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.llm_client import llm_client
from config import settings
from models import Document
from utils.logger import logger


async def get_text_embedding(text: str) -> list[float]:
    """调用云端大模型，将文本转换为向量"""
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
    RAG检索工具：
    问题向量化 -> 向量粗排 -> Reranker精排 -> 返回正文和来源文件
    """
    logger.info(f" [RAG工具] 开始检索内部知识库: '{query}'")

    try:
        # ==========================================
        # 1. 向量化问题
        # ==========================================
        query_vector = await get_text_embedding(query)

        # ==========================================
        # 2. 粗排阶段
        # ==========================================
        stmt = (
            select(Document.content, Document.metadata_info)
            .order_by(Document.embedding.cosine_distance(query_vector))
            .limit(settings.recall_top_k)
        )

        result = await db.execute(stmt)
        recall_rows = result.all()

        if not recall_rows:
            return "未找到相关内部资料。"

        recall_items = []

        for content, metadata_info in recall_rows:
            metadata_info = metadata_info or {}
            source = metadata_info.get("source", "未知来源")
            source_file_name = os.path.basename(source)

            recall_items.append({
                "content": content,
                "source": source_file_name
            })

        logger.info(f" [RAG工具] 粗排召回 {len(recall_items)} 条，开始重排...")

        # ==========================================
        # 3. Reranker精排
        # ==========================================
        try:
            safe_chunks = [item["content"][:350] for item in recall_items]
            safe_query = query[:100]

            async with httpx.AsyncClient() as client:
                payload = {
                    "model": settings.reranker_model,
                    "query": safe_query,
                    "documents": safe_chunks,
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

            results = rerank_data.get("results", [])
            final_chunks = []

            # ==========================================
            # 4. 根据重排结果找回原始正文和来源
            # ==========================================
            for item in results:
                relevance_score = item.get("relevance_score", 0)

                if relevance_score < settings.rerank_score_threshold:
                    continue

                selected_item = None
                result_index = item.get("index")

                if isinstance(result_index, int) and 0 <= result_index < len(recall_items):
                    selected_item = recall_items[result_index]

                if not selected_item:
                    document = item.get("document", {})
                    rerank_text = document.get("text", "")

                    for recall_item in recall_items:
                        safe_text = recall_item["content"][:350]

                        if safe_text == rerank_text:
                            selected_item = recall_item
                            break

                if selected_item:
                    final_chunks.append(
                        f"【来源文件：{selected_item['source']}】\n"
                        f"{selected_item['content']}"
                    )

            # ==========================================
            # 5. 分数阈值过严时保留第一名
            # ==========================================
            if not final_chunks and results:
                highest_score = results[0].get("relevance_score", 0)

                logger.warning(
                    f" Reranker过滤太严苛 "
                    f"(最高分仅{highest_score:.3f}，低于阈值)，触发弹性兜底。"
                )

                first_result = results[0]
                first_item = None
                first_index = first_result.get("index")

                if isinstance(first_index, int) and 0 <= first_index < len(recall_items):
                    first_item = recall_items[first_index]

                if not first_item:
                    document = first_result.get("document", {})
                    rerank_text = document.get("text", "")

                    for recall_item in recall_items:
                        safe_text = recall_item["content"][:350]

                        if safe_text == rerank_text:
                            first_item = recall_item
                            break

                if first_item:
                    final_chunks.append(
                        f"【来源文件：{first_item['source']}】\n"
                        f"{first_item['content']}"
                    )

            if not final_chunks:
                return "检索到的资料相关性过低，不予参考。"

            logger.info(f" [RAG工具] 精排完成，最终采纳了 {len(final_chunks)} 条资料。")
            return "\n\n".join(final_chunks)

        # ==========================================
        # 6. Reranker异常时降级返回粗排Top-3
        # ==========================================
        except httpx.TimeoutException:
            logger.warning(" [RAG防御矩阵] Reranker超时，降级返回粗排Top-3。")

            fallback_chunks = []

            for item in recall_items[:3]:
                fallback_chunks.append(
                    f"【来源文件：{item['source']}】\n"
                    f"{item['content']}"
                )

            return "\n\n".join(fallback_chunks)

        except Exception as e:
            logger.warning(f" [RAG防御矩阵] Reranker发生异常：{e}，降级返回粗排Top-3。")

            fallback_chunks = []

            for item in recall_items[:3]:
                fallback_chunks.append(
                    f"【来源文件：{item['source']}】\n"
                    f"{item['content']}"
                )

            return "\n\n".join(fallback_chunks)

    except Exception as e:
        logger.error(f" [RAG工具] 检索发生严重级崩溃：{e}", exc_info=True)
        return "内部知识库检索系统发生异常，暂无法提供资料。"
