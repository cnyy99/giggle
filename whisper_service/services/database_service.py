from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, Dict, Any
from utils.logger import setup_logger
from models.database import DatabaseManager, TranslationTask, TaskStatus

logger = setup_logger(__name__)


class DatabaseService:
    """数据库服务 - 负责任务状态的数据库操作"""

    def __init__(self, config):
        self.config = config
        self.db_manager = DatabaseManager(config.database_url)

    async def close(self):
        """关闭数据库连接"""
        await self.db_manager.close()

    async def update_task_status(self, task_id: str, status: str,
                                 result_path: str = None, error_message: str = None, accuracy: int = None,
                                 transcribed_text: str = None) -> bool:
        """更新任务状态"""
        try:
            async with self.db_manager.get_session() as session:
                # 构建更新数据
                update_data: Dict[str, Any] = {
                    'status': TaskStatus(status),
                    'updated_at': datetime.now(),
                    "accuracy": accuracy,
                    "text_content": transcribed_text,
                }

                if result_path:
                    update_data['result_file_path'] = result_path

                if error_message:
                    update_data['error_message'] = error_message

                # 执行更新
                stmt = (
                    update(TranslationTask)
                    .where(TranslationTask.id == task_id)
                    .values(**update_data)
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Task {task_id} status updated to {status} in database")
                    return True
                else:
                    logger.warning(f"Task {task_id} not found in database")
                    return False

        except Exception as e:
            logger.error(f"Failed to update task status in database: {e}")
            raise

    async def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        try:
            async with self.db_manager.get_session() as session:
                stmt = select(TranslationTask).where(TranslationTask.id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if task:
                    return {
                        'id': task.id,
                        'status': task.status.value,
                        'audio_file_path': task.audio_file_path,
                        'text_content': task.text_content,
                        'source_language': task.source_language,
                        'target_languages': task.target_languages,
                        'assigned_node_id': task.assigned_node_id,
                        'created_at': task.created_at,
                        'updated_at': task.updated_at,
                        'result_file_path': task.result_file_path,
                        'error_message': task.error_message,
                        'retry_count': task.retry_count
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get task details from database: {e}")
            return None

    async def update_task_assigned_node(self, task_id: str, node_id: str) -> bool:
        """更新任务分配的节点"""
        try:
            async with self.db_manager.get_session() as session:
                stmt = (
                    update(TranslationTask)
                    .where(TranslationTask.id == task_id)
                    .values(
                        assigned_node_id=node_id,
                        updated_at=datetime.now()
                    )
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Task {task_id} assigned to node {node_id}")
                    return True
                else:
                    logger.warning(f"Task {task_id} not found for node assignment")
                    return False

        except Exception as e:
            logger.error(f"Failed to update task assigned node: {e}")
            raise

    async def increment_retry_count(self, task_id: str) -> bool:
        """增加任务重试次数"""
        try:
            async with self.db_manager.get_session() as session:
                stmt = (
                    update(TranslationTask)
                    .where(TranslationTask.id == task_id)
                    .values(
                        retry_count=TranslationTask.retry_count + 1,
                        updated_at=datetime.now()
                    )
                )

                result = await session.execute(stmt)
                await session.commit()

                return result.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to increment retry count for task {task_id}: {e}")
            raise
