from typing import Union, Any, Optional
import time
import json
import requests

from fastapi import HTTPException
from fastapi.responses import Response
from starlette.responses import PlainTextResponse

from config import config
from utils.logger import logger

from weworkapi.callback_python3.WXBizMsgCrypt import WXBizMsgCrypt

wxcpt = WXBizMsgCrypt(sToken=config.sToken,sEncodingAESKey=config.sEncodingAESKey,sReceiveId=config.sCorpID)

def send_msg(msg: str, ToUserName: str, msg_id: str, agent_id: str, nonce: str, FromUserName: str = config.sCorpID) -> Any:
    """通过企业微信 API 主动发送消息"""
    try:
        # 获取 access_token
        access_token_url = f"{config.WeChatProxy}/cgi-bin/gettoken"
        params = {
            'corpid': config.sCorpID,
            'corpsecret': config.Secret
        }
        response = requests.get(access_token_url, params=params, verify=False)
        result = response.json()

        if result.get('errcode') != 0:
            logger.error(f"获取 access_token 失败: {result}")
            return None

        access_token = result.get('access_token')

        # 发送消息
        message_url = f"{config.WeChatProxy}/cgi-bin/message/send?access_token={access_token}"
        data = {
            'touser': ToUserName,
            'msgtype': 'text',
            'agentid': config.AgentId,
            'text': {
                'content': msg
            }
        }

        response = requests.post(message_url, json=data, verify=False)
        result = response.json()

        if result.get('errcode') == 0:
            logger.info(f"消息发送成功: {msg}")
        else:
            logger.error(f"消息发送失败: {result}")

        return None

    except Exception as e:
        logger.error(f"发送消息时发生错误: {str(e)}", exc_info=True)
        return None


def decrypt_msg(sReqData: bytes, sReqMsgSig: str, sReqTimeStamp: str, sReqNonce: str) -> Any:
    ret,sMsg = wxcpt.DecryptMsg(sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
    if( ret!=0 ):
      logger.error(f"ERR: DecryptMsg ret: {ret}")
    return sMsg

def vocechat_verify() -> Any:
    """
    VoceChat验证响应
    """
    return {"status": "OK"}

def wechat_verify(echostr: str, msg_signature: str, timestamp: Union[str, int], nonce: str,
                  source: Optional[str] = None) -> Any:
    try:
        ret, sEchoStr = wxcpt.VerifyURL(sMsgSignature=msg_signature, sTimeStamp=timestamp, sNonce=nonce, sEchoStr=echostr)
    
        if ret == 0:
            return PlainTextResponse(sEchoStr)
        return "微信验证失败"
    
    except Exception as err:
        logger.error(f"微信请求验证失败: {str(err)}", exc_info=True)
        return str(err)