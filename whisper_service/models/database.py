from sqlalchemy import Column, String, Text, DateTime, Integer, Enum as SQLEnum, Double
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime
from enum import Enum
from typing import Optional

Base = declarative_base()

class TaskStatus(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TranslationTask(Base):
    """翻译任务模型"""
    __tablename__ = 'translation_tasks'
    
    id = Column(String(255), primary_key=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    audio_file_path = Column(String(500), nullable=True)
    text_content = Column(Text, nullable=True)
    source_language = Column(String(10), nullable=False)
    target_languages = Column(String(500), nullable=False)
    assigned_node_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    result_file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    accuracy = Column(Double, nullable=True, default=0)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            echo=False,  # 设置为True可以看到SQL语句
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def close(self):
        """关闭数据库连接"""
        await self.engine.dispose()
    
    def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        return self.async_session()