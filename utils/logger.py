import logging
import sys
from pathlib import Path


def setup_logger(name: str = "musicdl", level: int = logging.INFO) -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # 添加处理器到日志器
    logger.addHandler(console_handler)

    return logger


# 创建全局日志实例
logger = setup_logger()