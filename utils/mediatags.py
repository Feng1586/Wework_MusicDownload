"""歌词与封面的落盘。

两件事，都是**尽力而为**，任何一步失败都不该影响「这首歌下载成功了」这个结论：

1. 在音频文件旁写**同名伴随文件**（`歌名.lrc` / `歌名.jpg`）——
   绝大多数播放器认同名的歌词和封面，而且不需要动音频文件本身；
2. 用 `mutagen` 把歌词和封面**嵌入音频标签**，让文件自包含、换机器也不丢。

用同名而不是 `cover.jpg`／`folder.jpg`：后端给的 work_dir 是
`QQMusicClient/<时间戳> 歌名/`，同一批次目录里可能落好几首歌，
固定名字的封面图会互相覆盖。

关于编码（踩过坑的两处）
------------------------
* `.lrc` 写 **UTF-8 无 BOM**。这是现在的事实标准；如果你的播放器显示乱码，
  改成 `utf-8-sig`（Windows 老播放器）或 GBK 即可，就在 `write_sidecars` 里。
* MP3 的 ID3 存成 **v2.3 + UTF-16 文本（encoding=1）**。
  v2.3 是国内播放器兼容性最好的一档，而 v2.3 规范里文本要用 UTF-16；
  用 UTF-8 虽然 mutagen 不拦，但部分老旧播放器会显示乱码。
"""
from __future__ import annotations

import os
import re
from typing import Optional

import requests

from utils.logger import logger

# 封面下载：读超时收紧一点。一张 170KB 的图正常不到 1 秒，
# 而这个调用发生在「✅ 下载完成」之前（见 download_queue._run_job 的说明），
# 所以最坏情况要有个上限：connect 10 + read 15 = 25 秒。
COVER_TIMEOUT_SECONDS = (10, 15)
# 防御：封面不该有这么大，避免坏 URL 拖垮队列
COVER_MAX_BYTES = 5 * 1024 * 1024

LRC_SUFFIX = '.lrc'
COVER_SUFFIX = '.jpg'

# musicdl 取不到歌词时会留这几个哨兵值，别把它们写成文件
_NULL_LYRIC = {'', 'null', 'none', 'NULL'}


def _clean_tag_value(value: Optional[str]) -> str:
    """去掉会破坏 LRC 标签的方括号。"""
    return (value or '').replace('[', '').replace(']', '').strip()


def _fill_empty_lrc_tags(lyric: str, song_name: Optional[str], singers: Optional[str]) -> str:
    """补上 LRC 里空的 ``[ti:]`` / ``[ar:]``。

    QQ 返回的歌词经常是 ``[ti:青花瓷][ar:][al:我很忙]``，[ar] 空着，
    播放器就显示不出歌手。只在原本为空时填，不覆盖已有内容。
    """
    title, artist = _clean_tag_value(song_name), _clean_tag_value(singers)
    if title:
        lyric = re.sub(r'\[ti:\s*\]', lambda _m: f'[ti:{title}]', lyric, count=1)
    if artist:
        lyric = re.sub(r'\[ar:\s*\]', lambda _m: f'[ar:{artist}]', lyric, count=1)
    return lyric


def fetch_cover(url: Optional[str]) -> Optional[bytes]:
    """下载封面图，失败返回 None。

    实测 y.gtimg.cn 的图**不需要任何请求头**就能取到（HTTP 200 / image/jpeg）。
    不抛异常：封面拿不到只是少个附带资源，不该让下载失败。
    """
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=COVER_TIMEOUT_SECONDS, verify=False)
        if resp.status_code != 200:
            logger.warning("封面下载失败：HTTP %s（%s）", resp.status_code, url)
            return None
        data = resp.content
        if not data:
            logger.warning("封面下载失败：内容为空（%s）", url)
            return None
        if len(data) > COVER_MAX_BYTES:
            logger.warning("封面超过 %d 字节，放弃（%s）", COVER_MAX_BYTES, url)
            return None
        # JPEG 魔数，防止拿到一个 HTML 错误页
        if not data.startswith(b'\xff\xd8\xff'):
            logger.warning("封面不是 JPEG，放弃（前 4 字节 %r）", data[:4])
            return None
        logger.info("封面已下载（%d 字节）", len(data))
        return data
    except Exception as e:
        logger.warning("封面下载异常：%s", e)
        return None


def write_sidecars(audio_path: str, lyric: Optional[str],
                   cover_bytes: Optional[bytes]) -> dict:
    """写同名 `.lrc` / `.jpg`，返回实际写出的路径。"""
    written = {'lrc': None, 'jpg': None}
    base = os.path.splitext(audio_path)[0]

    if lyric:
        path = base + LRC_SUFFIX
        try:
            with open(path, 'w', encoding='utf-8', newline='\n') as fp:
                fp.write(lyric if lyric.endswith('\n') else lyric + '\n')
            written['lrc'] = path
        except OSError as e:
            logger.warning("写歌词文件失败 %s：%s", path, e)

    if cover_bytes:
        path = base + COVER_SUFFIX
        try:
            with open(path, 'wb') as fp:
                fp.write(cover_bytes)
            written['jpg'] = path
        except OSError as e:
            logger.warning("写封面文件失败 %s：%s", path, e)

    return written


# --- 嵌入音频标签 -----------------------------------------------------------

def _embed_flac(path: str, lyric: Optional[str], cover_bytes: Optional[bytes]) -> None:
    from mutagen.flac import FLAC, Picture

    audio = FLAC(path)
    if lyric:
        # LYRICS 是通用写法，UNSYNCEDLYRICS 是另一批播放器认的，两个都放
        audio['LYRICS'] = [lyric]
        audio['UNSYNCEDLYRICS'] = [lyric]
    if cover_bytes:
        picture = Picture()
        picture.type = 3           # 3 = Cover (front)
        picture.mime = 'image/jpeg'
        picture.desc = 'Cover'
        picture.data = cover_bytes
        audio.clear_pictures()
        audio.add_picture(picture)
    audio.save()


def _embed_mp3(path: str, lyric: Optional[str], cover_bytes: Optional[bytes]) -> None:
    from mutagen.id3 import APIC, ID3, USLT, ID3NoHeaderError

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()               # 裸 mp3，新建一份标签

    if lyric:
        tags.delall('USLT')
        # encoding=1 -> UTF-16，ID3v2.3 规范里对中文的正确编码
        tags.add(USLT(encoding=1, lang='chi', desc='', text=lyric))
    if cover_bytes:
        tags.delall('APIC')
        tags.add(APIC(encoding=1, mime='image/jpeg', type=3, desc='Cover',
                      data=cover_bytes))

    # v2_version=3：国内播放器兼容性最好的一档
    tags.save(path, v2_version=3)


def _embed_mp4(path: str, lyric: Optional[str], cover_bytes: Optional[bytes]) -> None:
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(path)
    if lyric:
        audio['\xa9lyr'] = [lyric]
    if cover_bytes:
        audio['covr'] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


# 只覆盖 QQ 源实际会给出的格式；其余格式只写伴随文件
_EMBEDDERS = {
    '.flac': _embed_flac,
    '.mp3': _embed_mp3,
    '.m4a': _embed_mp4,
    '.mp4': _embed_mp4,
}


def embed_tags(audio_path: str, lyric: Optional[str],
               cover_bytes: Optional[bytes]) -> bool:
    """把歌词/封面嵌进音频标签，成功返回 True。

    这里**不抛异常**。注意 FLAC 在元数据空间不足时会把整个文件重写一遍，
    所以这个调用在大文件上可能耗几秒 —— 出问题也不该让任务算失败，
    伴随文件早就独立写好了。
    """
    if not lyric and not cover_bytes:
        return False

    ext = os.path.splitext(audio_path)[1].lower()
    embedder = _EMBEDDERS.get(ext)
    if embedder is None:
        logger.info("格式 %s 不支持嵌入标签，只保留伴随文件", ext or '(无扩展名)')
        return False

    try:
        embedder(audio_path, lyric, cover_bytes)
        return True
    except Exception as e:
        logger.warning("嵌入音频标签失败（%s）：%s", os.path.basename(audio_path), e)
        return False


def save_lyrics_and_cover(audio_path: str, lyric: Optional[str] = None,
                          cover_url: Optional[str] = None,
                          song_name: Optional[str] = None,
                          singers: Optional[str] = None) -> dict:
    """给一首已下载好的歌补上歌词与封面。返回一个简报字典（仅供日志）。

    顺序：先写伴随文件（几乎不会失败），再尝试嵌入标签（可能失败）。
    这样即使嵌入炸了，用户至少还有 .lrc / .jpg。
    """
    if lyric and lyric.strip().lower() in _NULL_LYRIC:
        lyric = None
    if lyric:
        lyric = _fill_empty_lrc_tags(lyric, song_name, singers)

    cover_bytes = fetch_cover(cover_url)
    written = write_sidecars(audio_path, lyric, cover_bytes)
    embedded = embed_tags(audio_path, lyric, cover_bytes)

    return {
        'lrc': bool(written['lrc']),
        'jpg': bool(written['jpg']),
        'embedded': embedded,
    }
