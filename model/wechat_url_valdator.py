from typing import Union, Any, Optional
import threading
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

# ---------------------------------------------------------------------------
# access_token 缓存
#
# access_token 有效期 7200 秒。之前每条消息都重新调一次 /cgi-bin/gettoken：
# 一是每次多一个公网往返、发消息明显变慢；二是企微对 gettoken 有频次限制，
# 高频获取还可能挤掉同一个 Secret 下的其他服务（换 token 会让旧 token 失效）。
# 所以这里缓存起来，并在过期前 5 分钟提前失效。
# ---------------------------------------------------------------------------
_token_lock = threading.Lock()
_token_cache = {'value': None, 'expire_at': 0.0}
TOKEN_EXPIRE_SKEW_SECONDS = 300
DEFAULT_TOKEN_TTL_SECONDS = 7200
REQUEST_TIMEOUT_SECONDS = 15

# 这些 errcode 表示 token 失效 / 非法，需要刷新后重试
_TOKEN_INVALID_ERRCODES = {40001, 40014, 41001, 42001}

# 企业微信 message/send 的特殊接收者：代表「该应用可见范围内的全体成员」
ALL_USERS = '@all'


def _fetch_access_token() -> Optional[str]:
    """向企微换取新的 access_token 并写入缓存。"""
    try:
        response = requests.get(
            f"{config.WeChatProxy}/cgi-bin/gettoken",
            params={'corpid': config.sCorpID, 'corpsecret': config.Secret},
            verify=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result = response.json()
    except Exception as e:
        logger.error(f"获取 access_token 请求异常: {e}", exc_info=True)
        return None

    if result.get('errcode') != 0:
        logger.error(f"获取 access_token 失败: {result}")
        return None

    access_token = result.get('access_token')
    try:
        expires_in = int(result.get('expires_in') or DEFAULT_TOKEN_TTL_SECONDS)
    except (TypeError, ValueError):
        expires_in = DEFAULT_TOKEN_TTL_SECONDS

    with _token_lock:
        _token_cache['value'] = access_token
        _token_cache['expire_at'] = time.time() + max(
            expires_in - TOKEN_EXPIRE_SKEW_SECONDS, 60
        )

    logger.info(f"access_token 已刷新，{expires_in} 秒后过期")
    return access_token


def _get_access_token(force: bool = False) -> Optional[str]:
    """取缓存里的 access_token；没有或已过期才去换新的。"""
    if not force:
        with _token_lock:
            if _token_cache['value'] and time.time() < _token_cache['expire_at']:
                return _token_cache['value']
    return _fetch_access_token()


def _post_text(touser: str, msg: str) -> bool:
    """给指定接收者发一条文本消息，token 失效时自动刷新重试一次。

    返回值只用于日志判断，调用方不依赖它。
    """
    try:
        # 最多两次：第一次用缓存 token，若报 token 失效就强制刷新再试一次
        for attempt in range(2):
            access_token = _get_access_token(force=attempt > 0)
            if not access_token:
                return False

            message_url = f"{config.WeChatProxy}/cgi-bin/message/send?access_token={access_token}"
            data = {
                'touser': touser,
                'msgtype': 'text',
                'agentid': config.AgentId,
                'text': {
                    'content': msg
                }
            }

            try:
                response = requests.post(
                    message_url, json=data, verify=False,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                result = response.json()
            except Exception as e:
                logger.error(f"发送消息请求异常: {e}", exc_info=True)
                return False

            errcode = result.get('errcode')
            if errcode == 0:
                # 只记接收者，不把正文打进日志（启动广播的正文很长）
                logger.info(f"消息发送成功 -> {touser}")
                return True

            if errcode in _TOKEN_INVALID_ERRCODES and attempt == 0:
                logger.warning(f"access_token 已失效（errcode={errcode}），刷新后重试")
                continue

            logger.error(f"消息发送失败（接收者 {touser}）: {result}")
            return False

        return False

    except Exception as e:
        logger.error(f"发送消息时发生错误: {str(e)}", exc_info=True)
        return False


def send_msg(msg: str, ToUserName: str, msg_id: str, agent_id: str, nonce: str, FromUserName: str = config.sCorpID) -> Any:
    """通过企业微信 API 主动给**单个成员**发送消息。

    签名保持原样（msg_id / agent_id / nonce 目前并未使用），避免改动所有调用方。
    """
    _post_text(ToUserName, msg)
    return None


def broadcast_message(msg: str) -> bool:
    """向**该应用可见范围内的全体成员**广播一条文本消息。

    企业微信 message/send 的特殊接收者 @all 即代表全量群发，
    具体能发到谁取决于该应用在后台设置的可见范围。
    """
    return _post_text(ALL_USERS, msg)


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
