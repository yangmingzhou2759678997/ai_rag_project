# 文件路径: services/knowledge_service.py
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Document
from tools.rag_tool import get_text_embedding
from utils.document_parser import extract_document
from utils.logger import logger
from utils.text_splitter import split_text


# ==========================================
# 功能 1：查找同名文件对应的旧知识片段
# ==========================================
async def get_same_file_documents(db: AsyncSession, file_name: str):
    """查询documents表，找出来源文件名相同的全部片段。"""
    stmt = select(Document)
    result = await db.execute(stmt)
    all_documents = result.scalars().all()
    same_file_documents = []

    for document in all_documents:
        metadata = document.metadata_info or {}
        source = metadata.get("source", "")
        source_file_name = os.path.basename(source)

        if source_file_name == file_name:
            same_file_documents.append(document)

    return same_file_documents


# ==========================================
# 功能 2：上传文件并写入向量数据库
# ==========================================
async def save_knowledge_file(db: AsyncSession, file_name: str, file_content: bytes):
    """完成文本提取、通用切分、向量化和数据库写入。"""
    safe_file_name = os.path.basename(file_name)
    file_extension = os.path.splitext(safe_file_name)[1].lower().replace(".", "")
    allowed_extensions = []

    for item in settings.allowed_extensions.split(","):
        allowed_extensions.append(item.strip().lower())

    # 第一步：校验文件类型
    if file_extension not in allowed_extensions:
        raise ValueError(f"不支持.{file_extension}文件，只允许上传：{', '.join(allowed_extensions)}")

    # 第二步：校验文件大小
    if len(file_content) > settings.max_upload_size:
        max_size_mb = settings.max_upload_size // 1024 // 1024
        raise ValueError(f"文件大小不能超过{max_size_mb}MB")

    # 第三步：把不同格式统一转换成普通文本
    raw_text = extract_document(safe_file_name, file_content)

    if not raw_text or not raw_text.strip():
        raise ValueError("没有从文件中提取到有效文本")

    # 第四步：所有格式都使用同一个文本切分器
    text_chunks = split_text(text=raw_text, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)

    if not text_chunks:
        raise ValueError("文件切分后没有生成有效文本片段")

    try:
        # 第五步：删除同名文件的旧片段，避免重复入库
        old_documents = await get_same_file_documents(db, safe_file_name)

        for old_document in old_documents:
            await db.delete(old_document)

        # 第六步：逐个片段生成向量并写入数据库
        for index, chunk in enumerate(text_chunks):
            logger.info(f" [知识库服务] 正在处理文件 {safe_file_name} | 片段 {index + 1}/{len(text_chunks)}")
            embedding_vector = await get_text_embedding(chunk)
            metadata_info = {
                "source": safe_file_name,
                "file_type": file_extension,
                "chunk_index": index
            }
            new_document = Document(content=chunk, embedding=embedding_vector, metadata_info=metadata_info)
            db.add(new_document)

        # 第七步：全部成功后统一提交事务
        await db.commit()
        logger.info(f" [知识库服务] 文件 {safe_file_name} 写入完成，共 {len(text_chunks)} 个片段")

        return {
            "file_name": safe_file_name,
            "file_type": file_extension,
            "chunk_count": len(text_chunks)
        }
    except Exception as error:
        await db.rollback()
        logger.error(f" [知识库服务] 文件写入失败：{error}", exc_info=True)
        raise


# ==========================================
# 功能 3：查看知识库文件列表
# ==========================================
async def get_knowledge_file_list(db: AsyncSession):
    """根据metadata_info统计当前知识库中的文件和片段数量。"""
    stmt = select(Document)
    result = await db.execute(stmt)
    all_documents = result.scalars().all()
    file_dict = {}

    for document in all_documents:
        metadata = document.metadata_info or {}
        source = metadata.get("source", "未知来源")
        file_name = os.path.basename(source)
        file_type = metadata.get("file_type", "txt")

        if file_name not in file_dict:
            file_dict[file_name] = {
                "file_name": file_name,
                "file_type": file_type,
                "chunk_count": 0
            }

        file_dict[file_name]["chunk_count"] += 1

    return list(file_dict.values())


# ==========================================
# 功能 4：删除指定知识库文件
# ==========================================
async def delete_knowledge_file(db: AsyncSession, file_name: str):
    """根据文件名删除该文件对应的全部知识片段。"""
    safe_file_name = os.path.basename(file_name)

    try:
        same_file_documents = await get_same_file_documents(db, safe_file_name)

        for document in same_file_documents:
            await db.delete(document)

        await db.commit()
        logger.info(f" [知识库服务] 删除文件 {safe_file_name}，共删除 {len(same_file_documents)} 个片段")
        return len(same_file_documents)
    except Exception as error:
        await db.rollback()
        logger.error(f" [知识库服务] 删除文件失败：{error}", exc_info=True)
        raise
