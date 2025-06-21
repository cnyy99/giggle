import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

@dataclass
class Config:
    # 节点配置
    NODE_ID: str = os.getenv('NODE_ID', 'whisper-node-1')
    HOST: str = os.getenv('HOST', 'localhost')
    PORT: int = int(os.getenv('PORT', '8001'))
    
    # Redis配置
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_PASSWORD: str = os.getenv('REDIS_PASSWORD', '')
    REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
    
    # 数据库配置
    DB_HOST: str = os.getenv('DB_HOST', 'localhost')
    DB_PORT: int = int(os.getenv('DB_PORT', '3306'))
    DB_NAME: str = os.getenv('DB_NAME', 'giggle_translation')
    DB_USER: str = os.getenv('DB_USER', 'root')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')
    
    # Whisper配置
    WHISPER_MODEL_SIZE: str = os.getenv('WHISPER_MODEL_SIZE', 'large-v3')
    
    # 翻译配置
    TRANSLATION_API_KEY: str = os.getenv('TRANSLATION_API_KEY', '')
    SUPPORTED_LANGUAGES: List[str] = field(default_factory=lambda: ['en', 'zh-cn', 'zh-tw', 'ja', 'ko', 'fr', 'de', 'es'])
    
    # 系统配置
    MAX_CONCURRENT_TASKS: int = int(os.getenv('MAX_CONCURRENT_TASKS', '3'))
    HEARTBEAT_INTERVAL: int = int(os.getenv('HEARTBEAT_INTERVAL', '30'))
    TASK_TIMEOUT: int = int(os.getenv('TASK_TIMEOUT', '1800'))  # 30分钟
    
    # GPU配置
    GPU_MEMORY_THRESHOLD: float = float(os.getenv('GPU_MEMORY_THRESHOLD', '0.8'))
    
    # Google翻译配置
    GOOGLE_TRANSLATE_API_KEY: str = os.getenv('GOOGLE_TRANSLATE_API_KEY', '')
    
    # Bing翻译配置
    BING_TRANSLATE_API_KEY: str = os.getenv('BING_TRANSLATE_API_KEY', '')
    BING_TRANSLATE_REGION: str = os.getenv('BING_TRANSLATE_REGION', 'global')
    
    # DeepL翻译配置
    DEEPL_API_KEY: str = os.getenv('DEEPL_API_KEY', '')
    DEEPL_API_URL: str = os.getenv('DEEPL_API_URL', 'https://api-free.deepl.com')  # 免费版API，付费版使用 https://api.deepl.com
    
    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"