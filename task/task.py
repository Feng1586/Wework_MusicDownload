import os
import requests
from cachetools import TTLCache

import hashlib

from musicdl import musicdl
from musicdl.modules.utils.misc import IOUtils, sanitize_filepath
from model.wechat_url_valdator import send_msg
from utils.logger import logger
from utils.version import __version__

from config import config

cache = TTLCache(maxsize=1000, ttl=60)

music_client = musicdl.MusicClient(music_sources=config.src_names,init_music_clients_cfg = config.init_music_clients_cfg)

# 接口地址列表，按优先级排序
API_ENDPOINTS = [
    "https://musicdownloads.i-am-a.gay:3000/music/search/qq",  # 宝塔 nginx 反向代理（HTTPS）
    "http://zd.i-am-a.gay:38001/music/search/qq",               # 直连接口
]

# 当前使用的接口索引
_current_api_index = 0

# 后端在「未授权 / 限流 / 服务登录中」时返回的是**结构相同**的占位数据，
# 唯一区别是 download_url 恒为字符串 "null"（不是 None，也不是缺失）。
#
# 这里必须把两种「没有下载地址」区分开，语义完全不同：
#   'null'  —— 后端明确告诉你服务不可用（未授权/限流/登录中），必须原样转达用户；
#   None/'' —— musicdl 对真实存在但取不到地址的歌就是给 None，属于「真没结果」，
#              这种情况才应该触发本地兜底搜索。
# 只判 `is None` 是最初的 bug：会把占位数据当成正常搜索结果，
# 用户看到一首叫「此程序为付费应用」的歌，回复 ID 后还会收到
# "Invalid URL 'null'" 这种看不懂的报错。
PLACEHOLDER_DOWNLOAD_URL = 'null'
INVALID_DOWNLOAD_URLS = (None, '', PLACEHOLDER_DOWNLOAD_URL)


def _is_placeholder(song: dict) -> bool:
    """该条目是不是后端的占位响应（未授权 / 限流 / 服务登录中）。"""
    return song.get('download_url') == PLACEHOLDER_DOWNLOAD_URL


def _is_downloadable(song: dict) -> bool:
    """该条目是否带有真正可用的下载地址。"""
    return song.get('download_url') not in INVALID_DOWNLOAD_URLS


def _format_notice(song: dict) -> str:
    """把后端占位条目里的提示文案（放在 song_name / singers 上）拼成一行。"""
    parts = [x for x in (song.get('song_name'), song.get('singers')) if x]
    return '：'.join(parts)


def generate_machine_code():

    Secret = config.Secret
    
    # 组合并哈希
    raw_string = Secret
    machine_code = hashlib.sha256(raw_string.encode()).hexdigest()
    
    return machine_code

def _build_song_info(song: dict, all_songs: list) -> dict:
    """构建歌曲信息字典"""
    return {
        'id': len(all_songs) + 1,
        'singers': song.get('singers', '未知'),
        'song_name': song.get('song_name', '未知'),
        'duration': song.get('duration', '00:00'),
        'source': song.get('source', '未知'),
        'download_url': song.get('download_url'),
        'ext': song.get('ext', 'mp3'),
        'work_dir': song.get('work_dir', './downloads')
    }


def _call_search_api(payload: dict) -> dict:
    """调用搜索API，自动切换接口地址"""
    global _current_api_index
    
    max_retries = len(API_ENDPOINTS)
    
    for attempt in range(max_retries):
        try:
            api_url = API_ENDPOINTS[_current_api_index]
            logger.info(f"尝试使用接口 {_current_api_index + 1}/{len(API_ENDPOINTS)}: {api_url}")
            
            response = requests.post(api_url, json=payload, timeout=60)
            response.raise_for_status()  # 检查HTTP状态码
            
            # 如果成功，返回结果
            return response.json()
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            logger.warning(f"接口 {_current_api_index + 1} 调用失败: {e}")
            
            # 切换到下一个接口
            _current_api_index = (_current_api_index + 1) % len(API_ENDPOINTS)
            
            if attempt < max_retries - 1:
                logger.info(f"切换到下一个接口: {API_ENDPOINTS[_current_api_index]}")
            else:
                logger.error("所有接口都尝试失败")
                raise
    
    # 理论上不会执行到这里
    return {}


def _is_download_ids(content: str) -> bool:
    """判断用户输入是否为下载ID（纯数字或逗号分隔的数字列表）"""
    parts = [x.strip() for x in content.split(',')]
    return all(p.isdigit() for p in parts) and len(parts) > 0


def _handle_download(content: str, ToUserName: str, nonce: str, msg_id: str, agent_id: str) -> None:
    """处理歌曲下载逻辑"""
    if not cache.get(ToUserName):
        send_msg(msg="请先搜索歌曲", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
        return

    all_songs = cache[ToUserName]
    ids = [int(x.strip()) for x in content.split(',')]

    for idx in ids:
        song_info = next((s for s in all_songs if s['id'] == idx), None)

        if not song_info:
            logger.warning(f"ID {idx} 不存在，跳过。")
            continue

        logger.info(f"正在下载: {song_info['singers']} - {song_info['song_name']} ({song_info['source']})...")

        try:
            with requests.get(
                song_info['download_url'],
                headers=music_client.music_clients[song_info['source']].default_download_headers,
                stream=True,
                verify=False
            ) as resp:
                if resp.status_code == 200:
                    total_size = int(resp.headers.get('content-length', 0))
                    chunk_size = 1024
                    download_size = 0

                    IOUtils.touchdir(song_info['work_dir'])

                    filename = f"{song_info['song_name']}.{song_info['ext']}"
                    save_path = sanitize_filepath(os.path.join(song_info['work_dir'], filename))

                    with open(save_path, 'wb') as fp:
                        for chunk in resp.iter_content(chunk_size=chunk_size):
                            if not chunk:
                                continue
                            fp.write(chunk)
                            download_size += len(chunk)
                            if total_size > 0:
                                percent = int(download_size / total_size * 100)
                                print(f"\r进度: {percent}%", end='')

                    send_msg(msg="下载成功", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
                else:
                    send_msg(msg="下载失败，请稍后再试", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)

        except Exception as e:
            logger.error(f"下载出错: {e}", exc_info=True)
            send_msg(msg=f"下载出错: {str(e)}", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)


def _handle_search(content: str, ToUserName: str, nonce: str, msg_id: str, agent_id: str) -> None:
    """处理歌曲搜索逻辑"""
    logger.info("执行搜索")

    try:
        # 尝试在线搜索，使用自动切换接口
        payload = {"keyword": content, "mechine_ID": generate_machine_code()}
        search_results = _call_search_api(payload)

        all_songs = []
        msg = ""
        notices = []

        # 只把「真的有下载地址」的条目放进列表和缓存，保证列表里的每个编号都能下载
        for source, songs in search_results.items():
            for song in songs:
                # 后端占位响应：只收集提示文案，绝不作为结果
                if _is_placeholder(song):
                    notice = _format_notice(song)
                    if notice:
                        notices.append(notice)
                    continue
                # 真实条目但取不到地址（musicdl 对这类歌给 None）：跳过，后面走本地兜底
                if not _is_downloadable(song):
                    continue
                song_info = _build_song_info(song, all_songs)
                all_songs.append(song_info)
                msg = msg + f"{song_info['id']}. {song_info['singers']}, {song_info['song_name']} \n"

        # 一条可下载的都没有，但后端给了提示（未授权 / 限流 / 服务登录中）：
        # 这是服务端明确的答复，此时**不能**回退本地搜索 —— 那等于绕过机器码授权。
        # 把后端的提示原样告诉用户，比笼统的「未找到相关歌曲」有用得多。
        if not all_songs and notices:
            logger.warning(f"后端返回占位响应: {notices}")
            send_msg(msg="\n".join(notices), ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            return

        # 真的没有结果，或结果里没有任何可下载地址，尝试使用本地搜索
        if not all_songs:
            logger.warning("在线搜索结果无下载链接，尝试使用本地搜索结果")
            local_results = music_client.search(keyword=content)
            for source, songs in local_results.items():
                for song in songs:
                    if not _is_downloadable(song):
                        continue
                    song_info = _build_song_info(song, all_songs)
                    all_songs.append(song_info)
                    msg = msg + f"{song_info['id']}. {song_info['singers']}, {song_info['song_name']} \n"

        if not all_songs:
            send_msg(msg="未找到相关歌曲", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
        else:
            msg = msg + "请回复最前面的数字ID进行下载"
            cache[ToUserName] = all_songs
            send_msg(msg=msg, ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            
    except Exception as e:
        logger.error(f"搜索接口调用失败: {e}", exc_info=True)
        send_msg(msg="搜索服务暂时不可用，请稍后再试", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)


def task(content: str, ToUserName: str, nonce: str, msg_id: str, agent_id: str) -> None:
    # 事件类回调等没有正文的消息直接忽略，避免后面 content.startswith 抛 AttributeError
    if not content:
        logger.warning("收到空消息，忽略")
        return

    # 以 / 开头的特殊指令分支
    if content.startswith('/'):
        command = content[1:].strip().lower()
        logger.info(f"收到指令: /{command}")

        if command == 'code':
            code = generate_machine_code()
            send_msg(msg=f"机器码: {code}", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            return
        
        if command == 'version':
            send_msg(msg=f"Version: {__version__}", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            return

        if command == 'help':
            help_msg = "指令列表:\n/code - 获取机器码\n/version - 显示版本信息\n/status - 查看接口状态\n/help - 显示帮助信息\n其他输入将被视为搜索关键词或下载ID"
            send_msg(msg=help_msg, ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            return

        if command == 'status':
            status_msg = f"接口状态:\n当前使用接口: {_current_api_index + 1}/{len(API_ENDPOINTS)}\n"
            for i, endpoint in enumerate(API_ENDPOINTS):
                prefix = "→ " if i == _current_api_index else "  "
                status_msg += f"{prefix}{i+1}. {endpoint}\n"
            send_msg(msg=status_msg, ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
            return

        # TODO: 在此处扩展更多指令处理，例如 /list、/cancel 等
        send_msg(msg=f"未知指令: /{command}", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
        return

    # 判断是否为下载ID（纯数字或逗号分隔的数字列表）
    if _is_download_ids(content):
        _handle_download(content, ToUserName, nonce, msg_id, agent_id)
    else:
        # 非数字，执行搜索
        _handle_search(content, ToUserName, nonce, msg_id, agent_id)
