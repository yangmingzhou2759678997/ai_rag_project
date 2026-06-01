import re
from utils.logger import logger


# ==========================================
# 核心工具：纯手工打造的“滑动窗口”文本切割器
# ==========================================
def split_text(text: str, chunk_size: int = 300, chunk_overlap: int = 50) -> list[str]:
    """
    工业级文本切分器
    作用：将长篇大论的文档，切分成适合大模型和向量库消化的短片段。

    :param text: 需要切分的原始长文本
    :param chunk_size: 每一块的最大字数（比如 300 字）
    :param chunk_overlap: 相邻两块之间的重叠字数（比如 50 字），防止关键句子被从中间拦腰截断
    :return: 一个装满短文本的列表
    """

    # 1. 基础兜底校验：如果传入的文本是空的，直接返回空列表，防止后端程序崩溃
    if not text or not text.strip():
        logger.warning("⚠️ 收到空文本，跳过切割动作。")
        return []

    # 2. 数据清洗 (极其重要)：
    # 把文本里多余的换行符 (\n)、连在一起的无数个空格，全部统一替换成一个单空格。
    # 因为在向量化 (Embedding) 时，换行符属于“无意义的噪音”，会严重影响检索准确率！
    clean_text = re.sub(r'\s+', ' ', text).strip()

    # 3. 准备一个空列表，用来充当装“文本切块”的篮子
    chunks = []

    # 4. 获取清洗后文本的总字数，心里有个底
    text_length = len(clean_text)

    # 5. 游标初始化：定义一个指针（start），代表当前这一刀从哪里开始切
    start = 0

    # 6. 开启切割循环：只要游标还没有走到文本的尽头，就一直切下去
    while start < text_length:
        # 7. 计算这一刀的终点：起点 + 你规定的每块大小 (chunk_size)
        end = start + chunk_size

        # 8. 字符串切片：把 [起点 到 终点] 的这段文字“截取”下来，装进篮子里
        chunk = clean_text[start:end]
        chunks.append(chunk)

        # 9. 🚨 核心算法：滑动窗口的精髓！
        # 游标往前挪。如果只是 start = start + chunk_size，那就是硬切，两块之间没有联系。
        # 我们减去 chunk_overlap，强行让游标往后退一点，这样下一块的开头，就会包含上一块的结尾！
        start = start + chunk_size - chunk_overlap

    # 10. 切割完毕，用你写好的企业级 logger 汇报战况，然后把装满碎片的篮子交出去
    logger.info(
        f"✂️ 文本切割完毕：总长度 {text_length} 字，共切出 {len(chunks)} 块 (滑动窗口={chunk_size}, 重叠={chunk_overlap})。")
    return chunks