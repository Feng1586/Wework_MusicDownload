"""启动广播的文案。

单独放一个模块，是为了以后想改文案时不用动 main.py。
文案是发到企业微信聊天里的纯文本，不支持 Markdown，
所以分隔线、序号这些只能用普通字符拼。
"""
from __future__ import annotations

import datetime

from utils.version import __version__

# 企业微信文本消息上限 2048 字节（一个汉字 3 字节），这条大约 600 字节，留足余量
_SEP = '━━━━━━━━━━━━━━━━━━'


def build_startup_notice() -> str:
    """构造「服务已启动」的广播文案。"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    return (
        f"🎵 MusicDL 已启动\n"
        f"\n"
        f"当前版本：v{__version__}\n"
        f"启动时间：{now}\n"
        f"\n"
        f"{_SEP}\n"
        f"📖 使用教程\n"
        f"{_SEP}\n"
        f"① 搜索资源\n"
        f"　直接发送歌曲名称，例如：青花瓷\n"
        f"② 下载资源\n"
        f"　回复资源列表最前面的数字，例如：1\n"
        f"　一次下载多首，用英文逗号分隔，例如：1,3,5\n"
        f"\n"
        f"{_SEP}\n"
        f"⌨️ 快捷指令\n"
        f"{_SEP}\n"
        f"/help　查看帮助\n"
        f"/version　查看版本\n"
        f"/status　查看接口状态\n"
        f"/code　获取机器码\n"
        f"\n"
        f"💡 搜索结果 60 秒内有效，请及时回复数字下载"
    )
