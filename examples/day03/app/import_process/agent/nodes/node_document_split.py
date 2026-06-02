import sys

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState

"""
   完成md内容的切块！ 
   最终： chunks -> 存储块的集合   chunks ->  备份到本地 -> chunks.json 
   1. 参数校验 
   2. 粗粒度切割（md）语义完善 -》 使用标题切割 
   3. 特殊场景，一个文档没有标题，我们给他一个默认标题
   4. 细粒度切割（md）大小和重叠合适 -> 大 -》（设置重叠） 小 || 小 -》 合并  
      大小合适，语义完整的chunks 
   5. 数据的备份和chunks属性的修改
   返回 state 
"""


def node_document_split(state: ImportGraphState) -> ImportGraphState:
    """
    节点: 文档切分 (node_document_split)
    为什么叫这个名字: 将长文档切分成小的 Chunks (切片) 以便检索。
    未来要实现:
    1. 基于 Markdown 标题层级进行递归切分。
    2. 对过长的段落进行二次切分。
    3. 生成包含 Metadata (标题路径) 的 Chunk 列表。
    """
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")
    return state