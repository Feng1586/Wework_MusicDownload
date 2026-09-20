from typing import Union, Any, Optional
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import PlainTextResponse
import xmltodict
from cachetools import TTLCache

from model.wechat_url_valdator import wechat_verify, vocechat_verify, decrypt_msg
from task.task import task
from utils.logger import logger

router = APIRouter()

# 消息去重缓存，600秒内重复的消息直接忽略
processed_messages = TTLCache(maxsize=1000, ttl=600)


def _ok() -> PlainTextResponse:
    """企业微信要求回调返回 success 字符串表示处理成功。"""
    return PlainTextResponse(content="success")


def _run_task(**kwargs) -> None:
    """
    在后台线程里执行消息处理。

    异常必须在这里吃掉：Starlette 的后台任务如果抛异常，只会污染日志，
    但它发生在响应返回之后，没有任何地方能兜住，这里统一记清楚。
    """
    try:
        task(**kwargs)
    except Exception as e:
        logger.error(f"后台任务执行失败: {str(e)}", exc_info=True)


@router.post("/wechat/callback")
async def wechat_callback(request: Request, background_tasks: BackgroundTasks):
    try:
        # 获取请求参数
        body = await request.body()
        msg_signature = request.query_params.get("msg_signature")
        timestamp = request.query_params.get("timestamp")
        nonce = request.query_params.get("nonce")

        if not all([msg_signature, timestamp, nonce]):
            logger.warning("缺少必要的参数")
            raise HTTPException(status_code=400, detail="缺少必要的参数")

        sMsg = decrypt_msg(body, msg_signature, timestamp, nonce)

        if not sMsg:
            logger.error("消息解密失败")
            raise HTTPException(status_code=400, detail="消息解密失败")

        xml_dict = xmltodict.parse(sMsg)
        logger.info(f"收到消息: {xml_dict}")
        xml_content = xml_dict.get('xml')

        if not xml_content:
            logger.error("XML内容解析失败")
            raise HTTPException(status_code=400, detail="XML内容解析失败")

        from_user_name = xml_content.get('FromUserName')
        msg_type = xml_content.get('MsgType')
        content = xml_content.get('Content')
        msg_id = xml_content.get('MsgId')
        agent_id = xml_content.get('AgentID')

        # 只处理文本消息。事件类回调（进入应用、菜单点击等）没有 MsgId，
        # Content 也可能为 None；之前这些会走到下面而抛 400/500，
        # 企微收到非 200 会判定失败并重试三次，制造无意义的重复请求。
        if msg_type != 'text' or not content:
            logger.info(f"忽略非文本消息: MsgType={msg_type}")
            return _ok()

        if not msg_id:
            logger.warning("文本消息缺少 MsgId，忽略")
            return _ok()

        logger.info(f"消息内容: {content}")

        # 检查消息是否已处理过（600秒内）
        if msg_id in processed_messages:
            logger.info(f"消息 {msg_id} 已处理过，忽略重复请求")
            return _ok()

        # 标记消息为已处理
        processed_messages[msg_id] = True

        # 企微要求回调 5 秒内返回，而搜索（超时 60 秒）和下载耗时远超这个限制。
        # 所以这里立即返回 success，真正的处理丢到后台，结果仍由 send_msg 主动推送。
        background_tasks.add_task(
            _run_task,
            content=content,
            ToUserName=from_user_name,
            nonce=nonce,
            msg_id=msg_id,
            agent_id=agent_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        # 解密之后的处理出错也不回 500：企微会把非 200 当失败并重试三次。
        # 失败信息本来就通过 send_msg 告知用户了，这里只记录日志。
        logger.error(f"处理消息时发生错误: {str(e)}", exc_info=True)

    # 企业微信要求返回 "success" 字符串表示处理成功
    return _ok()


@router.get("/wechat/callback", summary="回调请求验证")
def incoming_verify(token: Optional[str] = None, echostr: Optional[str] = None, msg_signature: Optional[str] = None,
                    timestamp: Union[str, int] = None, nonce: Optional[str] = None, source: Optional[str] = None) -> Any:
    logger.info(f"收到验证请求: token={token}, echostr={echostr}, "
          f"msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")
    
    if echostr and msg_signature and timestamp and nonce:
        return wechat_verify(echostr, msg_signature, timestamp, nonce, source)
    return vocechat_verify()
