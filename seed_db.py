# 文件路径: seed_db.py
import asyncio
import os

from database import AsyncSessionLocal  # 注意：这里导入的是你的会话工厂类，如果是其他名字请修改
from models import Document
from utils.text_splitter import split_text
from tools.rag_tool import get_text_embedding
from utils.logger import logger


# ==========================================
# 核心脚本：离线知识库向量化灌注 (ETL Pipeline)
# ==========================================
async def seed_database():
    """
    数据灌注主流程
    作用：读取本地 TXT 文件 -> 切割 -> 调大模型变成向量 -> 存入 PGVector
    """
    logger.info("🚀 [Seed DB] 开始执行离线知识库灌注任务...")

    # ---------------------------------------------------------
    # 零、准备测试数据（如果没文件，自动造一个给你测试）
    # ---------------------------------------------------------
    file_path = "company_manual.txt"
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ 未找到 {file_path}，系统正在为您自动生成一份测试数据...")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("【公司请假制度】\n员工每年享有10天带薪年假。请假超过3天需部门经理审批，超过7天需VP审批。\n\n"
                    "【公司报销制度】\n出差餐补标准为每天150元。打车费用凭发票实报实销，需在出差结束后一周内提交至财务部。\n\n"
                    "【办公网络指南】\n访客WIFI密码为：Welcome2026。内部员工请连接Corp_5G，使用域账号登录。")

    # ---------------------------------------------------------
    # 第一步：Extract (提取) - 读取本地文件内容
    # ---------------------------------------------------------
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            raw_text = file.read()
        logger.info(f"📄 [第一步] 成功读取源文件，总字数: {len(raw_text)}")
    except Exception as e:
        logger.error(f"❌ 读取文件失败: {e}")
        return

    # ---------------------------------------------------------
    # 第二步：Transform (转换 1) - 滑动窗口文本分块
    # 因为大模型的处理窗口有限，我们必须把长文切成一段段的 Chunk
    # ---------------------------------------------------------
    text_chunks = split_text(text=raw_text, chunk_size=100, chunk_overlap=20)
    logger.info(f"✂️ [第二步] 文本切分完毕，共切出 {len(text_chunks)} 个片段。")

    # ---------------------------------------------------------
    # 准备脱离 FastAPI，手动连接数据库
    # ---------------------------------------------------------
    async with AsyncSessionLocal() as db:
        # 开启一个数据库大事务
        try:
            # 遍历每一个切好的文本片段
            for index, chunk in enumerate(text_chunks):
                # ---------------------------------------------------------
                # 第三步：Transform (转换 2) - 文本向量化 (Embedding)
                # 调用我们在 rag_tool 里写好的工具，把这段中文变成 1024 维的浮点数组
                # ---------------------------------------------------------
                logger.info(f"🧠 [第三步] 正在将片段 {index + 1}/{len(text_chunks)} 转换为向量...")
                embedding_vector = await get_text_embedding(chunk)

                # ---------------------------------------------------------
                # 第四步：Load (加载) - 包装成 ORM 模型并存入 PostgreSQL
                # ---------------------------------------------------------
                # 实例化 Document 对象 (models.py 里的表)
                new_doc = Document(
                    content=chunk,
                    embedding=embedding_vector,
                    # metadata 可以存出处，方便以后溯源是哪个文件来的
                    metadata_info={"source": file_path, "chunk_index": index}
                )

                # 放入数据库暂存区
                db.add(new_doc)

            # 所有片段处理完毕，一次性提交 (Commit) 写入硬盘
            await db.commit()
            logger.info("✅ [第四步] 所有文本及其向量已成功存入 PGVector 数据库！")

        except Exception as e:
            # 如果中间有任何一个片段报错（比如网络断了），全部回滚，保证数据库的绝对干净
            await db.rollback()
            logger.error(f"❌ 数据库写入失败，已触发自动回滚: {e}")


# ==========================================
# 离线脚本的启动入口
# ==========================================
if __name__ == "__main__":
    # 因为整个库是异步的，普通 Python 脚本不能直接运行 async 函数
    # 必须借用 asyncio.run() 强行启动事件循环
    asyncio.run(seed_database())