package com.giggle.translation.service

import com.giggle.translation.common.BaseService
import com.giggle.translation.model.NodeStatus
import jakarta.annotation.PostConstruct
import jakarta.annotation.PreDestroy
import org.springframework.data.redis.core.RedisTemplate
import org.springframework.stereotype.Service
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

@Service
class NodeHeartbeatListener(
    private val redisTemplate: RedisTemplate<String, String>,
    private val nodeManagerService: NodeManagerService
): BaseService() {
    private val executor: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()
    
    @PostConstruct
    fun startListening() {
        // 启动定时任务同步节点信息
        executor.scheduleWithFixedDelay({
            try {
                syncNodeInformation()
            } catch (e: Exception) {
                logger.error("Error syncing node information", e)
            }
        }, 0, 30, TimeUnit.SECONDS) // 每30秒同步一次
        
        logger.info("Node heartbeat listener started")
    }
    
    @PreDestroy
    fun stopListening() {
        executor.shutdown()
        try {
            if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                executor.shutdownNow()
            }
        } catch (e: InterruptedException) {
            executor.shutdownNow()
        }
        logger.info("Node heartbeat listener stopped")
    }
    
    private fun syncNodeInformation() {
        try {
            // 获取所有活跃节点ID
            val activeNodeIds = redisTemplate.opsForSet().members("active_nodes") ?: emptySet()
            
            for (nodeId in activeNodeIds) {
                syncSingleNode(nodeId)
            }
            

        } catch (e: Exception) {
            logger.error("Failed to sync node information", e)
        }
    }
    
    private fun syncSingleNode(nodeId: String) {
        try {
            val nodeKey = "worker_nodes:$nodeId"
            val nodeInfo = redisTemplate.opsForHash<String, String>().entries(nodeKey)
            
            if (nodeInfo.isEmpty()) {
                logger.warn("No information found for node: $nodeId")
                // 从排名中移除不存在的节点
                nodeManagerService.removeNodeCompletely(nodeId)
                return
            }
            

            // 解析节点状态
            val status = when (nodeInfo["status"]?.uppercase()) {
                "ONLINE" -> NodeStatus.ONLINE
                "OFFLINE" -> NodeStatus.OFFLINE
                "BUSY" -> NodeStatus.BUSY
                "MAINTENANCE" -> NodeStatus.MAINTENANCE
                "SHUTTING_DOWN" -> NodeStatus.OFFLINE
                else -> NodeStatus.OFFLINE
            }
            
            // 如果节点离线，从排名中移除
            if (status == NodeStatus.OFFLINE) {
                nodeManagerService.removeNodeCompletely(nodeId)
            }
            
            logger.debug("Synced node $nodeId from Redis: status=$status")
            
        } catch (e: Exception) {
            logger.error("Failed to sync node $nodeId from Redis", e)
        }
    }
}