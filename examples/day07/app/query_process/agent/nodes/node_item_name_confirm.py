import sys
import os
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from mpmath import limit

from app.core.load_prompt import load_prompt
from app.query_process.agent.state import QueryGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.clients.mongo_history_utils import get_recent_messages, save_chat_message, update_message_item_names
from app.lm.lm_utils import get_llm_client
from app.lm.embedding_utils import generate_embeddings
from app.clients.milvus_utils import get_milvus_client, create_hybrid_search_requests, hybrid_search
from dotenv import load_dotenv,find_dotenv
from app.core.logger import logger

load_dotenv(find_dotenv())


def step_3_llm_item_name_and_rewrite_query(original_query, history_chats):
    """
    根据历史记录 -》 识别item_names 和 重写问题
    :param original_query: 用户原有的提问
    :param history_chats:  聊天记录
    :return:  {  item_name = [] , rewritten_query:问题
              }
    """
    # 1. 准备提示词
    history_text = ""
    for chat in history_chats:
        history_text += f"聊天角色：{chat['role']}，回答内容： {chat['text']}，重写问题： {chat['rewritten_query']}，关联主体： {','.join(chat['item_names'])},时间： {chat['ts']}\n"

    prompt = load_prompt("rewritten_query_and_itemnames",history_text=history_text,query= original_query)
    # 2. 模型调用
    lm_client = get_llm_client(json_mode=True)
    # system -> 模型的角色边界！ -> 应该是不变！  【角色，规则，格式】
    # user  ->  每次任务提示 -》 多条动态调整！  【提问/聊天】
    # 事实上，你嫌麻烦，你可以把模型的角色和边界写到user 功能也是完全一样！！
    messages = [
        HumanMessage(content=prompt)
    ]
    response = lm_client.invoke(messages)
    # 3. 结果解析
    content = response.content
    # json -> ```json   json  ```
    if content.startswith("```json"):
        content = content.replace("```json","").replace("```","")
    dict_content = json.loads(content)

    if "item_names" not in dict_content:
        dict_content["item_names"] = []
    if "rewritten_query" not in dict_content:
        dict_content["rewritten_query"] = original_query # 原提问
    # 4. 封装返回
    logger.info(f"已经完成问题的重写和item_name的提取！ 结果为：{dict_content}")
    return  dict_content

def node_item_name_confirm(state):
    """
    节点功能：确认用户问题中的核心商品名称。
    # 核心目标： 1. 提取【 item_name 】 （大模型从历史对话 + 本次提问 提取  -》 item_name -> 向量库搜索 ->  打分 -》 ABC）
               2. 利用模型重写用户的问题，确保后续查询召回率更高！！！
    # 核心参数： state['original_query' -> 用户的原问题 ]  ||  session_id
    # 响应数据： item_names: List[str]  # 提取出的商品名称
    #          rewritten_query: str  # 改写后的问题
    #          history: list  # 历史对话记录
        1. 获取历史条件记录（作为依据）
        2. 保存当前次的聊天记录
        3. 利用模型lm -> 1. 提取item_names  2.重写提问内容
        4. 进行item_name的向量数据库查询
        5. 对item_name结果进行打分分类处理 A 【确认集合】  B【可选集合】
        6. 处理确认和可选集合！ 有确认 =》 继续下个节点执行  || 有可选 or 没有item_names -> answer赋值结果
        7. 补充state状态 item_names rewritten_query  history
    """
    print(f"---node_item_name_confirm---开始处理")
    # 记录任务开始
    add_running_task(state["session_id"], sys._getframe().f_code.co_name,state["is_stream"])

    #  1. 获取历史条件记录（作为依据）
    history_chats = get_recent_messages(session_id=state["session_id"],limit=10)
    #  2. 保存当前次的聊天记录
    message_id = save_chat_message(
        session_id = state["session_id"],
        role = "user",
        text = state["original_query"],
        rewritten_query = state.get("rewritten_query",""),
        item_names = state.get("item_names",[]),
        image_urls = state.get("image_urls",[])
    )
    #  3. 利用模型lm -> 1. 提取item_names  2.重写提问内容
    #  参数： state["original_query"] || history_chats
    #  响应： { item_names : [] , rewritten_query : str }
    #  1. 为啥问题要重写？
    """
       1. 消除指代歧义    他 Ta 它 不明确！  明确查询主体 item_name
       2. 补全上下文     他的问题需要有历史记录支持！ 
       3. 去掉口语和冗余  同学们 同志们  为啥 咋弄 完犊子了 
       4. 润色问题增加召回率  模型查询的时候也会更精准
    """
    item_names_and_rewritten_query = step_3_llm_item_name_and_rewrite_query(state["original_query"],history_chats)


    # 记录任务结束
    add_done_task(state["session_id"], sys._getframe().f_code.co_name,state["is_stream"])
    print(f"---node_item_name_confirm---处理结束")

    return state