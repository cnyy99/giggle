import asyncio
import json
import psutil
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from utils.logger import setup_logger
from utils.gpu_utils import get_gpu_info, get_gpu_memory_usage
from services.database_service import DatabaseService

logger = setup_logger(__name__)

class NodeManager:
    """节点管理器 - 负责节点注册、心跳、任务获取等"""
    
    def __init__(self, config):
        self.config = config
        self.redis_client = None
        self.db_service = DatabaseService(config)  # 添加数据库服务
        self.running = True
        self.node_info = {
            'node_id': config.NODE_ID,
            'host': config.HOST,
            'port': config.PORT,
            'status': 'ONLINE',
            'active_task_count': 0,
            'max_concurrent_tasks': config.MAX_CONCURRENT_TASKS
        }
        self.cancelled_tasks = set()  # 存储已取消的任务ID
        
    async def _get_redis_client(self):
        """获取Redis客户端"""
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=self.config.REDIS_HOST,
                port=self.config.REDIS_PORT,
                password=self.config.REDIS_PASSWORD or None,
                db=self.config.REDIS_DB,
                decode_responses=True
            )
        return self.redis_client
    
    async def register_node(self):
        """注册节点到Redis"""
        try:
            redis_client = await self._get_redis_client()
            
            logger.info(f"Registering node {self.config.NODE_ID} to Redis at {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")
            
            # 更新节点信息
            await self._update_node_info()
            
            # 注册到Redis
            node_key = f"worker_nodes:{self.config.NODE_ID}"
            logger.debug(f"Setting node info in Redis with key: {node_key}")
            logger.debug(f"Node info to be registered: {self.node_info}")
            
            await redis_client.hset(node_key, mapping=self.node_info)
            await redis_client.expire(node_key, self.config.HEARTBEAT_INTERVAL * 3)
            
            # 添加到活跃节点集合
            await redis_client.sadd("active_nodes", self.config.NODE_ID)
            
            logger.info(f"Node {self.config.NODE_ID} registered successfully with host {self.config.HOST}:{self.config.PORT}")
            
        except Exception as e:
            logger.error(f"Failed to register node: {e}")
            raise
    
    async def unregister_node(self):
        """注销节点"""
        try:
            redis_client = await self._get_redis_client()
            
            # 从活跃节点集合中移除
            await redis_client.srem("active_nodes", self.config.NODE_ID)
            
            # 删除节点信息
            node_key = f"worker_nodes:{self.config.NODE_ID}"
            await redis_client.delete(node_key)
            
            # 清理任务队列
            queue_key = f"task_queue:{self.config.NODE_ID}"
            await redis_client.delete(queue_key)
            
            # 从节点排名中移除
            await redis_client.zrem("node_rankings", self.config.NODE_ID)
            
            logger.info(f"Node {self.config.NODE_ID} unregistered")
            if self.redis_client:
                await self.redis_client.close()
            self.redis_client = None
        except Exception as e:
            logger.error(f"Failed to unregister node: {e}")
    
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:  # 修改为检查running状态
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.config.HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(5)
    
    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            redis_client = await self._get_redis_client()
            
            # 更新节点信息
            await self._update_node_info()
            
            # 更新Redis中的节点信息
            node_key = f"worker_nodes:{self.config.NODE_ID}"
            logger.debug(f"Sending heartbeat to Redis with key: {node_key}")
            
            # 记录发送到Redis的数据
            await redis_client.hset(node_key, mapping=self.node_info)
            await redis_client.expire(node_key, self.config.HEARTBEAT_INTERVAL * 3)
            
            # 更新最后心跳时间
            current_time = datetime.now().isoformat()
            await redis_client.hset(node_key, "last_heartbeat", current_time)
            
            # 更新节点排名（如果节点在线）
            if self.node_info['status'] == 'ONLINE':
                await self._update_node_ranking(redis_client)
            
            logger.info(f"Heartbeat sent for node {self.config.NODE_ID} at {current_time}")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            raise
    
    async def _update_node_ranking(self, redis_client):
        """更新节点在有序集合中的排名"""
        try:
            # 计算节点评分（分数越低越优先）
            memory_percent = self.node_info.get('memory_percent', 100.0)
            cpu_usage = self.node_info.get('cpu_usage', 100.0)
            active_task_count = self.node_info.get('active_task_count', 10)
            
            # 权重配置
            memory_weight = 0.4
            cpu_weight = 0.3
            task_weight = 0.3
            
            # 计算综合评分（越低越好）
            memory_score = memory_percent / 100.0
            cpu_score = cpu_usage / 100.0
            task_score = min(active_task_count / 10.0, 1.0)
            
            score = memory_weight * memory_score + cpu_weight * cpu_score + task_weight * task_score
            
            # 更新有序集合中的排名
            await redis_client.zadd("node_rankings", {self.config.NODE_ID: score})
            
            logger.debug(f"Updated node ranking with score: {score:.3f}")
            
        except Exception as e:
            logger.error(f"Failed to update node ranking: {e}")
    
    async def _update_node_info(self):
        """更新节点信息"""
        try:
            # 获取系统信息
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 获取GPU信息
            gpu_info = get_gpu_info()
            gpu_memory = get_gpu_memory_usage()
            
            # 记录更新前的节点信息
            logger.debug(f"Current node info before update: {self.node_info}")
            
            self.node_info.update({
                'memory_total': memory.total,
                'memory_used': memory.used,
                'memory_percent': memory.percent,
                'cpu_usage': cpu_percent,
                'gpu_available': '1' if gpu_info.get('available', False) else '0',  # 将布尔值转换为字符串
                'gpu_memory_total': gpu_memory.get('total', 0),
                'gpu_memory_used': gpu_memory.get('used', 0),
                'gpu_memory_percent': gpu_memory.get('percent', 0),
                'last_update': datetime.now().isoformat()
            })
            
            # 记录更新后的节点信息
            logger.info(f"Node {self.config.NODE_ID} info updated: CPU: {cpu_percent}%, Memory: {memory.percent}%, GPU available: {gpu_info.get('available', False)}")
            logger.debug(f"Updated node info: {self.node_info}")
            
        except Exception as e:
            logger.error(f"Failed to update node info: {e}")
    
    async def get_task(self) -> Optional[Dict[str, Any]]:
        """从队列获取任务"""
        try:
            redis_client = await self._get_redis_client()
            queue_key = f"task_queue:{self.config.NODE_ID}"
            
            # 检查节点状态，如果是SHUTTING_DOWN或OFFLINE，不再获取新任务
            if self.node_info['status'] in ['SHUTTING_DOWN', 'OFFLINE']:
                logger.debug(f"Node is {self.node_info['status']}, not accepting new tasks")
                return None
            
            # 检查是否超过最大并发任务数
            if self.node_info['active_task_count'] >= self.config.MAX_CONCURRENT_TASKS:
                return None
            
            # 从队列获取任务
            task_data = await redis_client.brpop(queue_key, timeout=1)
            if task_data:
                _, task_json = task_data
                task = json.loads(task_json)
                
                # 分配任务给当前节点
                task_id = task.get('taskId')
                if task_id and await self.assign_task_to_node(task_id):
                    logger.info(f"Received and assigned task: {task_id}")
                    return task
                else:
                    logger.error(f"Failed to assign task {task_id} to node")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None
    
    async def assign_task_to_node(self, task_id: str):
        """将任务分配给当前节点"""
        try:
            success = await self.db_service.update_task_assigned_node(task_id, self.config.NODE_ID)
            if success:
                self.node_info['active_task_count'] += 1
                logger.info(f"Task {task_id} assigned to node {self.config.NODE_ID}")
            return success
        except Exception as e:
            logger.error(f"Failed to assign task {task_id} to node: {e}")
            return False
    
    async def update_task_status(self, task_id: str, status: str, 
                               result_path: str = None, error_message: str = None,accuracy: float = None,transcribed_text=None):
        """更新任务状态到数据库"""
        try:
            # 直接更新数据库
            success = await self.db_service.update_task_status(
                task_id, status, result_path, error_message,accuracy,transcribed_text
            )
            
            if success:
                # 如果任务完成或失败，减少活跃任务计数
                if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    if self.node_info['active_task_count'] > 0:
                        self.node_info['active_task_count'] -= 1
                
                logger.info(f"Task status updated in database: {task_id} -> {status}")
            else:
                logger.error(f"Failed to update task status for {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            raise
    
    async def update_node_status(self, status: str):
        """更新节点状态"""
        try:
            logger.info(f"Updating node {self.config.NODE_ID} status to: {status}")
            
            # 更新本地节点状态
            self.node_info['status'] = status
            
            # 如果状态是SHUTTING_DOWN或OFFLINE，停止接受新任务并从ranking中删除
            if status in ['SHUTTING_DOWN', 'OFFLINE']:
                self.running = False
                
                # 从节点排名中删除该节点
                redis_client = await self._get_redis_client()
                await redis_client.zrem("node_rankings", self.config.NODE_ID)
                logger.info(f"Removed node {self.config.NODE_ID} from rankings due to status: {status}")
            
            # 立即发送心跳以同步状态到Redis
            await self._send_heartbeat()
            
            logger.info(f"Node status updated to: {status}")
            
        except Exception as e:
            logger.error(f"Failed to update node status: {e}")
            raise
    
    async def stop(self):
        """停止节点管理器"""
        logger.info(f"Stopping node manager for {self.config.NODE_ID}")
        self.running = False
        
        # 更新节点状态为SHUTTING_DOWN
        self.node_info['status'] = 'SHUTTING_DOWN'
        
        try:
            # 发送最后一次心跳
            await self._send_heartbeat()
            
            # 注销节点
            await self.unregister_node()
            
        except Exception as e:
            logger.error(f"Error during node shutdown: {e}")
        
        logger.info(f"Node manager stopped for {self.config.NODE_ID}")
    
    async def close(self):
        """关闭节点管理器"""
        logger.info(f"Closing node manager for {self.config.NODE_ID}")
        await self.db_service.close()
        if self.redis_client:
            await self.redis_client.close()
    
    async def check_control_messages(self):
        """检查控制消息（如取消任务）"""
        try:
            while self.running:
                redis_client = await self._get_redis_client()
                control_queue = f"control_queue:{self.config.NODE_ID}"

                message = await redis_client.brpop(control_queue)
                if message:
                    _, message_data = message
                    control_msg = json.loads(message_data)

                    if control_msg.get('action') == 'CANCEL_TASK':
                        task_id = control_msg.get('taskId')
                        await self.handle_task_cancellation(task_id)

        except Exception as e:
            logger.error(f"Error checking control messages: {e}")
    
    async def handle_task_cancellation(self, task_id: str):
        """处理任务取消"""
        try:
            logger.info(f"Received cancellation request for task {task_id}")
            
            # 标记任务为已取消
            self.cancelled_tasks.add(task_id)
            
            # 更新数据库状态
            await self.update_task_status(task_id, 'CANCELLED')
            
            logger.info(f"Task {task_id} marked as cancelled")
            
        except Exception as e:
            logger.error(f"Error handling task cancellation for {task_id}: {e}")