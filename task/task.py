import os
import requests
from cachetools import TTLCache

import hashlib
import uuid
import socket
import subprocess
import platform

from musicdl import musicdl
from musicdl.modules.utils.misc import IOUtils, sanitize_filepath
from model.wechat_url_valdator import send_msg
from utils.logger import logger

from config import config

cache = TTLCache(maxsize=1000, ttl=60)

music_client = musicdl.MusicClient(music_sources=config.src_names,init_music_clients_cfg = config.init_music_clients_cfg)

url  = "http://musicdownloads.i-am-a.gay/music/search/qq"

def generate_machine_code():
    
    # 2. 获取主机名
    hostname = socket.gethostname()
    
    # 3. 获取MAC地址
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                   for elements in range(0, 8*6, 8)][::-1])
    
    # 4. 获取CPU信息
    cpu_info = platform.processor()
    
    # 5. 组合并哈希
    raw_string = f"{hostname}|{mac}|{cpu_info}"
    machine_code = hashlib.sha256(raw_string.encode()).hexdigest()
    
    return machine_code

def task(content: str, ToUserName: str, nonce: str, msg_id: str, agent_id: str) -> None:
    try:
        content = int(content)
        type(content)
        if cache[ToUserName]:
            all_songs = cache[ToUserName]
            # 解析用户输入的ID
            ids = [int(x.strip()) for x in str(content).split(',')]

            for idx in ids:
                # 查找对应的歌曲信息
                song_info = next((s for s in all_songs if s['id'] == idx), None)

                if not song_info:
                    logger.warning(f"ID {idx} 不存在，跳过。")
                    continue

                logger.info(f"正在下载: {song_info['singers']} - {song_info['song_name']} ({song_info['source']})...")

                try:
                    # 5. 执行下载
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

                            # 确保目录存在
                            IOUtils.touchdir(song_info['work_dir'])

                            # 构建文件路径
                            filename = f"{song_info['song_name']}.{song_info['ext']}"
                            save_path = sanitize_filepath(os.path.join(song_info['work_dir'], filename))

                            with open(save_path, 'wb') as fp:
                                for chunk in resp.iter_content(chunk_size=chunk_size):
                                    if not chunk:
                                        continue
                                    fp.write(chunk)
                                    download_size += len(chunk)
                                    # 简单的进度显示
                                    if total_size > 0:
                                        percent = int(download_size / total_size * 100)
                                        print(f"\r进度: {percent}%", end='')

                            send_msg(msg="下载成功", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
                        else:
                            send_msg(msg="下载失败，请稍后再试", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)

                except Exception as e:
                    logger.error(f"下载出错: {e}", exc_info=True)
                    send_msg(msg=f"下载出错: {str(e)}", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)

        else:
            send_msg(msg="请先搜索歌曲", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)

    except:
        logger.info("用户输入的不是数字，执行搜索")
        # search_results = music_client.search(keyword=content)
        #print(search_results)

        payload = {"keyword": content, "mechine_ID": generate_machine_code()}

        search_results = requests.post(url, json=payload).json()

        # 整理并展示搜索结果
        all_songs = []  # 存储整理后的歌曲信息（包含ID）
        msg = ""

        for source, songs in search_results.items():
            for song in songs:
                # 创建一个新的字典来存储信息，避免修改原始对象
                song_info = {
                    'id': len(all_songs) + 1,
                    'singers': song.get('singers', '未知'),
                    'song_name': song.get('song_name', '未知'),
                    'duration': song.get('duration', '00:00'),
                    'source': song.get('source', '未知'),
                    'download_url': song.get('download_url'),
                    'ext': song.get('ext', 'mp3'),
                    'work_dir': song.get('work_dir', './downloads')
                }
                all_songs.append(song_info)
                msg = msg + f"{song_info['id']}. {song_info['singers']}, {song_info['song_name']} \n"

        if not all_songs:
            send_msg(msg="未找到相关歌曲", ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)
        else:
            msg = msg + "请回复最前面的数字ID进行下载"
            cache[ToUserName] = all_songs
            send_msg(msg=msg, ToUserName=ToUserName, msg_id=msg_id, agent_id=agent_id, nonce=nonce)