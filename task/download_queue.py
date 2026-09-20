"""下载队列。

为什么要队列
------------
改动前，用户回复编号后是在同一个后台任务里**同步**把歌下完再回复，
而一首 flac 动辄一百多 MB，用户要等几十秒到几分钟才能继续搜索。
这个模块把「下载」从「回复的同步流程」里摘出来：

    task.py  解析编号 -> 入队 -> 立刻回一条「已加入下载队列」
    这里     worker 线程按 FIFO 顺序慢慢下，开始/结束各推一条消息

于是用户入队后可以马上继续搜索，两边互不阻塞。

几个刻意的设计
--------------
* **入队时快照**：job 里带的是那首歌的完整信息（含已归一化的 work_dir
  和下载请求头），而不是「记住编号、下载时再回查」。这样用户下一步搜索
  把结果缓存覆盖掉，也不影响已经排队的下载。
* **单 worker（``WORKER_COUNT``）**：严格 FIFO，对 QQ 侧也友好。
  ``queue.Queue`` 本身是线程安全的，想并发下载把这个常量调大即可。
* **懒启动 + daemon 线程**：没排队的进程不会白占线程；进程退出时 worker
  随主进程结束，此时还没下完的任务会丢 —— 可以接受，用户重新回复编号即可。
"""
from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass
from typing import Optional

import requests
from musicdl.modules.utils.misc import IOUtils, sanitize_filepath

from model.wechat_url_valdator import send_msg
from utils.logger import logger

# 同时下载几首。1 = 严格排队。
WORKER_COUNT = 1

# 下载是流式的：读超时是「两次收到数据之间」的上限，不是整个文件的耗时上限，
# 所以这里可以给得比较宽。没有超时的话，一个卡住的连接会把整个队列堵死。
DOWNLOAD_CONNECT_TIMEOUT_SECONDS = 15
DOWNLOAD_READ_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 1024


@dataclass
class DownloadJob:
    """一条待下载任务。字段全部是入队那一刻的快照。"""

    song: dict          # 已归一化的 song_info（含 id / song_name / singers / work_dir / ext / download_url）
    headers: dict       # 下载请求头
    touser: str         # 接收消息的成员
    msg_id: str
    agent_id: str
    nonce: str

    @property
    def title(self) -> str:
        """给用户看的「歌名-歌手」。"""
        return f"{self.song.get('song_name') or '未知'}-{self.song.get('singers') or '未知'}"

    def reply(self, msg: str) -> None:
        """给这条任务的发起人回一条消息。"""
        send_msg(msg=msg, ToUserName=self.touser, msg_id=self.msg_id,
                 agent_id=self.agent_id, nonce=self.nonce)


def format_size(num_bytes: int) -> str:
    """把字节数变成用户看得懂的大小，例如 156000000 -> '148.8 MB'。"""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = num_bytes / 1024
    for unit in ("KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class DownloadQueue:
    """下载队列本体。全局一个实例即可（见 task.py 末尾的 download_queue）。"""

    def __init__(self, worker_count: int = WORKER_COUNT) -> None:
        self._queue: queue.Queue[DownloadJob] = queue.Queue()
        self._worker_count = max(int(worker_count), 1)
        self._lock = threading.Lock()
        self._started = False
        # 正在下载的那几条。queue.qsize() 只统计「还没被 worker 取走」的任务，
        # worker 一旦 get() 走它就归零，所以队列长度必须自己把在飞的加上，
        # 否则下载进行中看起来像「队列已空」。
        self._inflight = 0

    # -- 对外接口 ---------------------------------------------------------

    def submit(self, job: DownloadJob) -> None:
        """入队一条任务。首次调用时才真正拉起 worker。"""
        self._ensure_started()
        self._queue.put(job)
        logger.info("已入队：%s（当前排队 %d 条）", job.title, self.pending())

    def pending(self) -> int:
        """还没处理完的任务数（含正在下载的）。"""
        with self._lock:
            return self._queue.qsize() + self._inflight

    # -- 内部实现 ---------------------------------------------------------

    def _ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            for index in range(self._worker_count):
                threading.Thread(
                    target=self._worker,
                    name=f"musicdl-download-{index + 1}",
                    daemon=True,
                ).start()
            self._started = True
            logger.info("下载队列已启动，worker 数 %d", self._worker_count)

    def _worker(self) -> None:
        while True:
            job = self._queue.get()
            with self._lock:
                self._inflight += 1
            try:
                self._run_job(job)
            except Exception as e:
                # 兜底：_run_job 内部已经处理过常规异常，走到这里说明是意料之外的问题，
                # 但绝不能让 worker 线程死掉，否则后面所有任务都没人处理。
                logger.error("下载任务异常: %s", e, exc_info=True)
            finally:
                with self._lock:
                    self._inflight -= 1
                self._queue.task_done()

    def _run_job(self, job: DownloadJob) -> None:
        job.reply(f"⚙️ 开始下载：{job.title}")

        try:
            save_path = self._download(job)
        except Exception as e:
            logger.error("下载失败 %s: %s", job.title, e, exc_info=True)
            job.reply(f"❌ 下载失败：{job.title}\n原因：{e}")
            return

        try:
            size = os.path.getsize(save_path)
        except OSError as e:
            logger.error("下载完成但读不到文件大小 %s: %s", save_path, e)
            size = 0

        # 报给用户的是磁盘上真实的名字 —— sanitize_filepath 可能改写过它，
        # 所以这里取 basename(save_path) 而不是拼接时的那个字符串。
        job.reply(f"✅ 下载完成：{os.path.basename(save_path)}\n💾 大小：{format_size(size)}")

    def _download(self, job: DownloadJob) -> str:
        """下载单首歌，返回落盘后的绝对/相对路径。"""
        song = job.song
        work_dir = song["work_dir"]
        IOUtils.touchdir(work_dir)

        filename = f"{song.get('song_name') or '未知'}.{song.get('ext') or 'mp3'}"
        save_path = sanitize_filepath(os.path.join(work_dir, filename))

        logger.info("开始下载 %s -> %s", job.title, save_path)

        with requests.get(
            song["download_url"],
            headers=job.headers,
            stream=True,
            verify=False,
            timeout=(DOWNLOAD_CONNECT_TIMEOUT_SECONDS, DOWNLOAD_READ_TIMEOUT_SECONDS),
        ) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"服务端返回 HTTP {resp.status_code}")

            total_size = int(resp.headers.get("content-length") or 0)
            downloaded = 0

            with open(save_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(downloaded / total_size * 100)
                        print(f"\r进度: {percent}%", end="")

        if downloaded == 0:
            # 200 但没内容（空响应/错误页）会让用户在「下载完成 0 B」上白等一场，
            # 明确当失败处理，并把半成品文件删掉。
            try:
                os.remove(save_path)
            except OSError:
                pass
            raise RuntimeError("下载内容为空")

        logger.info("下载完成 %s（%s 字节）", save_path, downloaded)
        return save_path


def make_headers(source_client) -> dict:
    """从 musicdl 的客户端实例上取下载请求头，取不到就返回空字典。

    取不到不直接抛异常：宁可少几个头也把歌下下来，日志里留痕即可。
    """
    headers: Optional[dict] = getattr(source_client, "default_download_headers", None)
    if not headers:
        logger.warning("未取到 download headers，将不带自定义请求头下载")
        return {}
    return dict(headers)


# 全局单例：task.py 只 import 这一个对象
download_queue = DownloadQueue()
