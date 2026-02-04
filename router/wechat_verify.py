from typing import Union, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
import xmltodict
from cachetools import TTLCache

from model.wechat_url_valdator import wechat_verify, vocechat_verify, decrypt_msg
from task.task import task
from schemas.models import Response
from utils.logger import logger

router = APIRouter()

# 消息去重缓存，600秒内重复的消息直接忽略
processed_messages = TTLCache(maxsize=1000, ttl=600)

@router.post("/wechat/callback")
async def wechat_callback(request: Request):
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

        to_user_name = xml_content.get('ToUserName')
        from_user_name = xml_content.get('FromUserName')
        create_time = xml_content.get('CreateTime')
        msg_type = xml_content.get('MsgType')
        content = xml_content.get('Content')
        msg_id = xml_content.get('MsgId')
        agent_id = xml_content.get('AgentID')

        if not msg_id:
            logger.warning("消息ID为空")
            raise HTTPException(status_code=400, detail="消息ID为空")

        logger.info(f"消息内容: {content}")

        # 检查消息是否已处理过（60秒内）
        if msg_id in processed_messages:
            logger.info(f"消息 {msg_id} 已处理过，忽略重复请求")
            return PlainTextResponse(content="success")

        # 标记消息为已处理
        processed_messages[msg_id] = True

        task(content=content,ToUserName=from_user_name,nonce=nonce,msg_id=msg_id,agent_id=agent_id)



    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

    # 企业微信要求返回 "success" 字符串表示处理成功
    return PlainTextResponse(content="success")


@router.get("/wechat/callback", summary="回调请求验证")
def incoming_verify(token: Optional[str] = None, echostr: Optional[str] = None, msg_signature: Optional[str] = None,
                    timestamp: Union[str, int] = None, nonce: Optional[str] = None, source: Optional[str] = None) -> Any:
    logger.info(f"收到验证请求: token={token}, echostr={echostr}, "
          f"msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")
    
    if echostr and msg_signature and timestamp and nonce:
        return wechat_verify(echostr, msg_signature, timestamp, nonce, source)
    return vocechat_verify()

