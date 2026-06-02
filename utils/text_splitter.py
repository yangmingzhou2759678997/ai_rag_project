import re
from utils.logger import logger


def split_text(text: str, chunk_size: int = 350, chunk_overlap: int = 50) -> list[str]:
    """工业级语义切分器：优先按段落切，段落太长再按字数切"""
    if not text or not text.strip():
        return []

    # 第一步：按自然段落（双换行符）粗切
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = re.sub(r'\s+', ' ', para).strip()  # 清洗多余空格
        if not para:
            continue

        # 如果当前块加上新段落还没超标，就拼在一起
        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += para + "\n"
        else:
            # 如果超标了，先把现有的块存起来
            if current_chunk:
                chunks.append(current_chunk.strip())
            # 开启新块，并加上重叠内容（Overlap）防断层
            overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
            current_chunk = overlap_text + para + "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    logger.info(f"✂️ 语义切分完毕：共切出 {len(chunks)} 块高质量片段。")
    return chunks