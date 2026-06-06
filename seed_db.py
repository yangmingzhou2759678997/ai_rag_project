# 覆盖替换文件路径: seed_db.py
import asyncio
from database import AsyncSessionLocal, async_engine
from models import Document
from utils.text_splitter import split_text
from tools.rag_tool import get_text_embedding
from utils.logger import logger


async def seed_database():
    logger.info("🚀 [Seed DB] 开始执行离线知识库灌注任务...")
    file_path = "data/company_knowledge.txt"
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            raw_text = file.read()
    except Exception as e:
        logger.error(f"❌ 读取文件失败: {e}")
        return

    text_chunks = split_text(text=raw_text, chunk_size=350, chunk_overlap=50)
    logger.info(f"✂️ [第二步] 文本切分完毕，共切出 {len(text_chunks)} 个片段。")

    async with AsyncSessionLocal() as db:
        try:
            for index, chunk in enumerate(text_chunks):
                logger.info(f"🧠 [第三步] 正在将片段 {index + 1}/{len(text_chunks)} 转换为向量...")
                embedding_vector = await get_text_embedding(chunk)

                new_doc = Document(
                    content=chunk,
                    embedding=embedding_vector,
                    metadata_info={"source": file_path, "chunk_index": index}
                )
                db.add(new_doc)

            await db.commit()
            logger.info("✅ [第四步] 所有文本及其向量已成功存入 PGVector 数据库！")
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ 数据库写入失败，已触发自动回滚: {e}")

    # 🚨 终极修复：彻底粉碎“事件循环撕裂”报错，主动释放全局连接池
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())