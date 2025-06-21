import asyncio
import signal
import sys
from services.node_manager import NodeManager
from services.whisper_service import WhisperService
from services.translation_service import TranslationService
from services.text_packer import SimplifiedTextPacker
from utils.logger import setup_logger
from config import Config

logger = setup_logger(__name__)


class WhisperWorker:
    def __init__(self,):
        self.config = Config()
        self.node_manager = NodeManager(self.config)
        self.whisper_service = WhisperService(self.config)
        self.translation_service = TranslationService(self.config)
        self.text_packer = SimplifiedTextPacker()
        self.running = True
        self.active_tasks = 0
        self.shutdown_event = asyncio.Event()
        self.running_tasks = set()  # 添加任务集合管理

    async def start(self):
        """启动工作节点"""
        logger.info(f"Starting Whisper worker node {self.config.NODE_ID}")

        try:
            # 注册节点
            await self.node_manager.register_node()

            # 启动心跳任务
            heartbeat_task = asyncio.create_task(self.node_manager.heartbeat_loop())

            # 启动任务处理循环
            task_processor = asyncio.create_task(self.process_tasks())

            check_control_messages = asyncio.create_task(self.node_manager.check_control_messages())
            # 等待任务完成
            await asyncio.gather(heartbeat_task, task_processor, check_control_messages)

        except Exception as e:
            logger.error(f"Error starting worker: {e}")
            raise
        finally:
            # 关闭连接
            await self.node_manager.close()

    async def handle_task(self, task_data):
        """处理单个翻译任务"""
        task_id = task_data['taskId']
        logger.info(f"Processing task {task_id}")

        # 检查任务是否已被取消
        if task_id in self.node_manager.cancelled_tasks:
            logger.info(f"Task {task_id} was cancelled before processing")
            return

        self.active_tasks += 1
        logger.info(f"Started new task, active tasks: {self.active_tasks}")

        try:
            # 更新任务状态为处理中
            await self.node_manager.update_task_status(task_id, 'PROCESSING')

            # 在每个主要步骤前检查取消状态
            if task_id in self.node_manager.cancelled_tasks:
                logger.info(f"Task {task_id} cancelled during processing")
                return

            # 语音转文字（如果有音频文件）
            transcribed_text = None
            accuracy = None
            if task_data.get('audioFilePath'):
                # 检查取消状态
                if task_id in self.node_manager.cancelled_tasks:
                    return

                transcribed_text = await self.whisper_service.transcribe(
                    task_data['audioFilePath'],
                    task_data['sourceLanguage']
                )
                logger.info(f"Transcribed text: {transcribed_text}")

            # 检查取消状态
            if task_id in self.node_manager.cancelled_tasks:
                logger.info(f"Task {task_id} cancelled during processing")
                return

            logger.info(f"calculate transcription accuracy:")

            # 翻译处理...
            # 正确性校验
            if task_data.get('originalText'):
                accuracy = self.calculate_accuracy(
                    task_data['originalText'],
                    transcribed_text
                )
                logger.info(f"Transcription accuracy: {accuracy:.2%}")

            logger.info(f"prepare translation_tasks")

            # 准备翻译任务
            translation_tasks = []

            # 1. 翻译原始文本（如果存在）
            original_translations = None
            if task_data.get('textContent') or task_data.get('originalText'):
                original_text = task_data.get('textContent') or task_data.get('originalText')
                translation_tasks.append((
                    'original',
                    self.translation_service.translate_text(
                        original_text,
                        task_data['sourceLanguage'],
                        task_data['targetLanguages']
                    )
                ))

            # 2. 翻译STT文本（如果存在）
            stt_translations = None
            if transcribed_text:
                translation_tasks.append((
                    'stt',
                    self.translation_service.translate_text(
                        transcribed_text,
                        task_data['sourceLanguage'],
                        task_data['targetLanguages']
                    )
                ))
            logger.info(f"running translation_tasks {task_id}")

            # 并发执行翻译任务 - 添加超时和取消检查
            if translation_tasks:
                try:
                    # 设置总体超时时间，避免无限等待
                    results = await asyncio.wait_for(
                        asyncio.gather(*[task[1] for task in translation_tasks], return_exceptions=True),
                        timeout=300.0  # 5分钟超时
                    )
                    
                    # 检查是否被取消
                    if task_id in self.node_manager.cancelled_tasks:
                        logger.info(f"Task {task_id} was cancelled during translation")
                        return
                    
                    # 处理结果，包括异常情况
                    for i, (task_type, _) in enumerate(translation_tasks):
                        result = results[i]
                        if isinstance(result, Exception):
                            logger.error(f"Translation task {task_type} failed: {result}")
                            # 根据任务类型设置默认值或跳过
                            if task_type == 'original':
                                original_translations = {}
                            elif task_type == 'stt':
                                stt_translations = {}
                        else:
                            if task_type == 'original':
                                original_translations = result
                            elif task_type == 'stt':
                                stt_translations = result
                                
                except asyncio.TimeoutError:
                    logger.error(f"Translation tasks timed out for task {task_id}")
                    # 设置默认值继续处理
                    original_translations = {}
                    stt_translations = {}
                except asyncio.CancelledError:
                    logger.info(f"Translation tasks cancelled for task {task_id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error in translation tasks for task {task_id}: {e}")
                    # 设置默认值继续处理
                    original_translations = {}
                    stt_translations = {}

            # 打包结果（包含两种翻译结果）
            packed_file = self.text_packer.pack_translations(
                task_id,
                original_text=task_data.get('textContent') or task_data.get('originalText'),
                original_translations=original_translations,
                stt_text=transcribed_text,
                stt_translations=stt_translations
            )

            # 上传结果并更新任务状态为完成
            result_path = await self.upload_result(task_id, packed_file)
            # 最终检查取消状态
            if task_id in self.node_manager.cancelled_tasks:
                return

            # 完成任务
            await self.node_manager.update_task_status(
                task_id, 'COMPLETED', result_path=result_path, accuracy=accuracy, transcribed_text=transcribed_text
            )

        except Exception as e:
            if task_id not in self.node_manager.cancelled_tasks:
                logger.exception(f"Task {task_id} failed: {e}")
                await self.node_manager.update_task_status(
                    task_id, 'FAILED', error_message=str(e)
                )
        finally:
            # 清理取消标记
            self.node_manager.cancelled_tasks.discard(task_id)
            self.active_tasks -= 1
            if self.active_tasks == 0 and not self.running:
                self.shutdown_event.set()

    async def process_tasks(self):
        """处理翻译任务 - 支持并发处理"""

        while self.running:
            try:
                # 清理已完成的任务
                self.running_tasks = {task for task in self.running_tasks if not task.done()}
                
                # 检查是否可以启动新任务
                if (self.running and
                    len(self.running_tasks) < self.config.MAX_CONCURRENT_TASKS):
                    
                    # 尝试获取新任务（非阻塞）
                    try:
                        task = await asyncio.wait_for(
                            self.node_manager.get_task(), 
                            timeout=1.0
                        )
                        
                        if task:
                            logger.info(f"received task: {task}")
                            # 使用 create_task 创建任务对象，并添加到管理集合
                            task_obj = asyncio.create_task(self.handle_task(task))
                            self.running_tasks.add(task_obj)
                            
                            # 添加完成回调，自动清理
                            task_obj.add_done_callback(lambda t: self.running_tasks.discard(t))

                    except asyncio.TimeoutError:
                        # 获取任务超时，继续循环
                        pass

                    # 没有运行中的任务时短暂休眠
                    await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.exception(f"Error in task processing loop: {e}")
                await asyncio.sleep(1)

    async def shutdown(self):
        """优雅关闭"""
        logger.info("Shutting down worker...")

        # 首先更新节点状态为SHUTTING_DOWN
        await self.node_manager.update_node_status('SHUTTING_DOWN')

        # 设置运行标志为False，停止接受新任务
        self.running = False
        self.node_manager.running = False

        # 等待所有运行中的任务完成
        if self.running_tasks:
            logger.info(f"Waiting for {len(self.running_tasks)} running tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.running_tasks, return_exceptions=True),
                    timeout=self.config.TASK_TIMEOUT
                )
                logger.info("All tasks completed successfully")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for tasks to complete after {self.config.TASK_TIMEOUT}s")
                # 取消未完成的任务
                for task in self.running_tasks:
                    if not task.done():
                        task.cancel()


    def calculate_accuracy(self, original, transcribed):
        """计算转录准确性"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, original.lower(), transcribed.lower()).ratio()

    async def upload_result(self, task_id, packed_data):
        """上传结果文件"""
        import os
        result_dir = f"/tmp/translation_results"
        os.makedirs(result_dir, exist_ok=True)

        result_path = f"{result_dir}/{task_id}.bin"
        with open(result_path, 'wb') as f:
            f.write(packed_data)

        return result_path

    async def shutdown(self):
        """优雅关闭"""
        logger.info("Shutting down worker...")

        # 首先更新节点状态为SHUTTING_DOWN，这会通过心跳同步到apigateway
        await self.node_manager.update_node_status('SHUTTING_DOWN')

        # 设置运行标志为False，停止接受新任务
        self.running = False
        self.node_manager.running = False

        if self.active_tasks > 0:
            logger.info(f"Waiting for {self.active_tasks} active tasks to complete...")
            try:
                # 等待所有任务完成，最多等待配置的任务超时时间
                await asyncio.wait_for(self.shutdown_event.wait(),
                                       timeout=self.config.TASK_TIMEOUT)
                logger.info("All tasks completed successfully")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for tasks to complete after {self.config.TASK_TIMEOUT}s")

        # 更新节点状态为OFFLINE
        await self.node_manager.update_node_status('OFFLINE')

        # 注销节点
        await self.node_manager.unregister_node()
        logger.info("Worker shutdown complete")


def signal_handler(worker):
    def handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(worker.shutdown())

    return handler


async def main():
    worker = WhisperWorker()

    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler(worker))
    signal.signal(signal.SIGTERM, signal_handler(worker))

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
        shutdown_task = asyncio.create_task(worker.shutdown())
        try:
            # 增加超时时间，给任务完成留出足够时间
            # 使用配置的任务超时时间加上一些额外时间
            timeout = worker.config.TASK_TIMEOUT + 30
            await asyncio.wait_for(shutdown_task, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out, forcing exit")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
