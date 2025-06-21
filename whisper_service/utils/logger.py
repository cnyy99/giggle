from loguru import logger
import sys
from datetime import datetime
import os

# 配置loguru
log_file = f'/tmp/whisper_service_{datetime.now().strftime("%Y%m%d")}.log'

# 移除默认处理器
logger.remove()

# 添加控制台处理器
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 添加文件处理器
logger.add(
    log_file,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="1 day",  # 每天轮换日志文件
    retention="7 days"  # 保留7天的日志
)

def setup_logger(name: str):
    """设置日志记录器，返回带有上下文的logger"""
    # 使用loguru的上下文功能，这样日志会包含模块名称
    return logger.bind(name=name)