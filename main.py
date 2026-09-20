import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import config
from utils.logger import logger
from utils.notice import build_startup_notice
from utils.version import __version__

# 监听地址与端口。默认值与历史行为一致（0.0.0.0:8000），
# 只是让 .env.example 里承诺的 HOST / PORT 真正能被读到。
HOST = os.environ.get('HOST') or "0.0.0.0"
PORT = int(os.environ.get('PORT') or 8000)

REQUIRED_CONFIG = (
    ('STOKEN', config.sToken),
    ('S_ENCODING_AES_KEY', config.sEncodingAESKey),
    ('S_CORP_ID', config.sCorpID),
    ('AGENT_ID', config.AgentId),
    ('SECRET', config.Secret),
    ('WECHAT_PROXY', config.WeChatProxy),
)

_missing_config = [name for name, value in REQUIRED_CONFIG if not value]

if _missing_config:
    # 镜像里不再打包任何真实凭据（凭据改由环境变量注入），所以必须把
    # 「缺配置」这件事明确喊出来，否则只会看到一个莫名其妙的 FormatException。
    logger.error(
        "以下配置为空，企业微信接入必然失败：%s。"
        "Docker 部署请在 docker-compose.yml 同目录的 .env 中补齐后重启容器；"
        "本机运行请填写 config/config.py 或设置同名环境变量。",
        ", ".join(_missing_config),
    )

# 注意：路由与消息发送模块在导入时就会用 sToken / SEncodingAESKey 构造企微加解密器，
# 配置非法时它会立刻抛异常。所以上面的自检必须写在这次导入之前，
# 否则日志里只会留下一句 FormatException，看不出到底缺了什么。
from router import wechat_verify  # noqa: E402
from model.wechat_url_valdator import broadcast_message  # noqa: E402


def _notify_all_users() -> None:
    """启动后向应用可见范围内的全体成员广播一条项目信息。

    刻意放后台线程：发送要走公网，最坏情况会耗掉两个 15 秒超时，
    不能让它卡住 uvicorn 的启动流程（健康检查也会跟着被推迟）。
    广播失败只记日志，不影响服务本身。
    """
    def worker() -> None:
        try:
            if broadcast_message(build_startup_notice()):
                logger.info("启动广播已发送给全体成员")
            else:
                logger.warning("启动广播发送失败，详见上面的错误日志")
        except Exception as e:
            logger.error(f"启动广播异常: {e}", exc_info=True)

    threading.Thread(target=worker, name="startup-notice", daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _missing_config:
        logger.warning("配置不完整，跳过启动广播")
    else:
        logger.info(f"配置检查通过，MusicDL v{__version__} 准备就绪")
        _notify_all_users()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(wechat_verify.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
