# 文件路径: routers/knowledge.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from security import get_current_user
from services import knowledge_service
from utils.logger import logger


# ==========================================
# 知识库管理路由
# ==========================================
router = APIRouter(
    prefix="/api/knowledge",
    tags=["知识库管理模块"]
)


# ==========================================
# 接口 1：上传知识库文件
# ==========================================
@router.post("/upload", summary="上传知识库文件")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    接收用户上传的知识文件，交给服务层完成：
    文本提取、文本切分、向量化和数据库写入。
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="上传的文件没有文件名"
        )

    try:
        # 第一步：读取上传文件的二进制内容
        file_content = await file.read()

        # 第二步：交给知识库服务层处理
        result = await knowledge_service.save_knowledge_file(
            db=db,
            file_name=file.filename,
            file_content=file_content
        )

        logger.info(
            f" [知识库路由] 用户 {current_user.id} "
            f"上传文件成功：{file.filename}"
        )

        return {
            "code": 200,
            "msg": "知识库文件上传成功",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f" [知识库路由] 文件上传失败：{e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="知识库文件处理失败，请查看后端日志"
        )
    finally:
        await file.close()


# ==========================================
# 接口 2：查看当前知识库文件列表
# ==========================================
@router.get("/documents", summary="查看知识库文件列表")
async def get_knowledge_documents(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    document_list = await knowledge_service.get_knowledge_file_list(db)

    logger.info(
        f" [知识库路由] 用户 {current_user.id} "
        f"查看知识库文件列表"
    )

    return {
        "code": 200,
        "data": document_list
    }


# ==========================================
# 接口 3：删除指定知识库文件
# ==========================================
@router.delete(
    "/documents/{file_name}",
    summary="删除指定知识库文件"
)
async def delete_knowledge_document(
    file_name: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    deleted_count = await knowledge_service.delete_knowledge_file(
        db=db,
        file_name=file_name
    )

    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="没有找到该知识库文件"
        )

    logger.info(
        f" [知识库路由] 用户 {current_user.id} "
        f"删除文件成功：{file_name}"
    )

    return {
        "code": 200,
        "msg": "知识库文件删除成功",
        "data": {
            "file_name": file_name,
            "deleted_chunk_count": deleted_count
        }
    }
