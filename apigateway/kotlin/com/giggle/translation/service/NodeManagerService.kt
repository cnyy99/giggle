package com.giggle.translation.service

import com.giggle.translation.model.NodeInfo
import com.giggle.translation.model.NodeStatus
import com.giggle.translation.utils.DistributedLock
import com.giggle.translation.model.*
import org.ktorm.dsl.*
import org.ktorm.entity.*
import org.ktorm.database.Database
import org.slf4j.LoggerFactory
import org.springframework.data.redis.core.RedisTemplate
import org.springframework.stereotype.Service
import java.time.LocalDateTime

@Service
class NodeManagerService(
    private val redisTemplate: RedisTemplate<String, String>,
    private val distributedLock: DistributedLock,
    private val database: Database // 添加数据库依赖
) {
    private val logger = LoggerFactory.getLogger(NodeManagerService::class.java)
    
    companion object {
        private const val NODE_RANKING_KEY = "node_rankings"
        private const val NODE_INFO_PREFIX = "worker_nodes:"
        private const val ACTIVE_NODES_KEY = "active_nodes"
    }
    
    fun getAvailableNodes(): List<NodeInfo> {
        return getAvailableNodesFromRedis()
    }
    
    private fun getAvailableNodesFromRedis(): List<NodeInfo> {
        try {
            // 首先清理失效节点
            cleanupInactiveNodes()
            
            val rankedNodeIds = redisTemplate.opsForZSet().range(NODE_RANKING_KEY, 0, -1)
            val availableNodes = mutableListOf<NodeInfo>()
            
            rankedNodeIds?.forEach { nodeId ->
                val nodeInfo = getNodeInfoFromRedis(nodeId)
                if (nodeInfo != null && isNodeAvailable(nodeInfo)) {
                    availableNodes.add(nodeInfo)
                } else {
                    // 如果节点信息无效或不可用，从排名和活跃节点中移除
                    removeInactiveNode(nodeId)
                }
            }
            
            logger.debug("Found ${availableNodes.size} available nodes from Redis")
            return availableNodes
        } catch (e: Exception) {
            logger.error("Failed to get nodes from Redis, falling back to database", e)
            return getAllNodesAsNodeInfo().filter { it.status == NodeStatus.ONLINE }
        }
    }
    
    private fun getNodeInfoFromRedis(nodeId: String): NodeInfo? {
        try {
            val nodeKey = "$NODE_INFO_PREFIX$nodeId"
            val nodeData = redisTemplate.opsForHash<String, String>().entries(nodeKey)
            
            if (nodeData.isEmpty()) {
                return null
            }
            
            // 解析节点信息并创建NodeInfo对象
            val host = nodeData["host"] ?: "unknown"
            val port = nodeData["port"]?.toIntOrNull() ?: 8001
            val memoryTotal = nodeData["memory_total"]?.toLongOrNull() ?: 0L
            val memoryUsed = nodeData["memory_used"]?.toLongOrNull() ?: 0L
            val cpuUsage = nodeData["cpu_usage"]?.toDoubleOrNull() ?: 0.0
            val gpuAvailable = nodeData["gpu_available"] == "1" || nodeData["gpu_available"]?.toBoolean() == true
            val activeTaskCount = nodeData["active_task_count"]?.toIntOrNull() ?: 0
            
            val status = when (nodeData["status"]?.uppercase()) {
                "ONLINE" -> NodeStatus.ONLINE
                "OFFLINE" -> NodeStatus.OFFLINE
                "BUSY" -> NodeStatus.BUSY
                "MAINTENANCE" -> NodeStatus.MAINTENANCE
                else -> NodeStatus.OFFLINE
            }
            
            return NodeInfo(
                nodeId = nodeId,
                host = host,
                port = port,
                memoryTotal = memoryTotal,
                memoryUsed = memoryUsed,
                cpuUsage = cpuUsage,
                gpuAvailable = gpuAvailable,
                status = status,
                lastHeartbeat = LocalDateTime.now(),
                activeTaskCount = activeTaskCount
            )
        } catch (e: Exception) {
            logger.error("Failed to get node info for $nodeId from Redis", e)
            return null
        }
    }
    
    /**
     * 清理失效节点，避免重复处理
     */
    private fun cleanupInactiveNodes() {
        try {
            val activeNodeIds = redisTemplate.opsForSet().members(ACTIVE_NODES_KEY) ?: emptySet()
            val rankedNodeIds = redisTemplate.opsForZSet().range(NODE_RANKING_KEY, 0, -1) ?: emptySet()
            
            // 找出在排名中但不在活跃节点集合中的节点
            val inactiveRankedNodes = rankedNodeIds - activeNodeIds
            
            inactiveRankedNodes.forEach { nodeId ->
                removeInactiveNode(nodeId)
                logger.info("Cleaned up inactive node $nodeId from rankings")
            }
            
            // 检查活跃节点集合中是否有已经失效的节点
            activeNodeIds.forEach { nodeId ->
                if (!isNodeHealthy(nodeId)) {
                    removeInactiveNode(nodeId)
                    logger.info("Removed unhealthy node $nodeId from active nodes")
                }
            }
            
        } catch (e: Exception) {
            logger.error("Failed to cleanup inactive nodes", e)
        }
    }
    
    /**
     * 移除失效节点的所有相关信息
     */
    private fun removeInactiveNode(nodeId: String) {
        try {
            // 从排名中移除
            redisTemplate.opsForZSet().remove(NODE_RANKING_KEY, nodeId)
            
            // 从活跃节点集合中移除
            redisTemplate.opsForSet().remove(ACTIVE_NODES_KEY, nodeId)
            
            logger.debug("Removed inactive node $nodeId from all Redis structures")
        } catch (e: Exception) {
            logger.error("Failed to remove inactive node $nodeId", e)
        }
    }

    fun removeNodeFromRanking(nodeId: String) {
        try {
            redisTemplate.opsForZSet().remove(NODE_RANKING_KEY, nodeId)
            logger.debug("Removed node $nodeId from ranking")
        } catch (e: Exception) {
            logger.error("Failed to remove node $nodeId from ranking", e)
        }
    }
    
    /**
     * 完全移除节点（包括从活跃节点集合中移除）
     */
    fun removeNodeCompletely(nodeId: String) {
        removeInactiveNode(nodeId)
        logger.info("Completely removed node $nodeId")
    }
    
    private fun isNodeAvailable(node: NodeInfo): Boolean {
        return node.status == NodeStatus.ONLINE
    }
    
    // 修改getAllNodesAsNodeInfo方法，从Redis获取所有节点
    fun getAllNodesAsNodeInfo(): List<NodeInfo> {
        return try {
            val allNodeIds = redisTemplate.keys("$NODE_INFO_PREFIX*")
                .map { it.removePrefix(NODE_INFO_PREFIX) }
            
            val allNodes = mutableListOf<NodeInfo>()
            allNodeIds.forEach { nodeId ->
                val nodeInfo = getNodeInfoFromRedis(nodeId)
                if (nodeInfo != null) {
                    allNodes.add(nodeInfo)
                }
            }
            
            logger.debug("Found ${allNodes.size} nodes from Redis")
            allNodes
        } catch (e: Exception) {
            logger.error("Failed to get all nodes from Redis", e)
            emptyList()
        }
    }
    
    // 修改selectOptimalNode方法，从Redis获取节点信息
    fun selectOptimalNode(task: Any): NodeInfo? {
        val selectionLockKey = "node_selection:${System.currentTimeMillis() % 5}"
        
        return distributedLock.withLock(selectionLockKey, expireTime = 3L, waitTime = 1L) {
            val availableNodeInfos = getAvailableNodes()
            
            // 从数据库查询每个节点的实际任务数量
            availableNodeInfos
                .map { node ->
                    val activeTaskCount = getActiveTaskCountFromDB(node.nodeId)
                    node.copy(activeTaskCount = activeTaskCount)
                }
                .filter { it.activeTaskCount < 10 } // 过滤掉满负载的节点
                .minByOrNull { 
                    it.cpuUsage + (it.memoryUsed.toDouble() / it.memoryTotal * 100) + (it.activeTaskCount * 10)
                }
        }
    }
    
    private fun getActiveTaskCountFromDB(nodeId: String): Int {
        return try {
            database.from(TranslationTasks)
                .select(count())
                .where { 
                    (TranslationTasks.assignedNodeId eq nodeId) and 
                    (TranslationTasks.status eq TaskStatus.PROCESSING)
                }
                .map { it.getInt(1) }
                .first()
        } catch (e: Exception) {
            logger.error("Failed to get active task count for node $nodeId from database", e)
            0
        }
    }
    
    // 修改isNodeHealthy方法，从Redis检查节点健康状态
    fun isNodeHealthy(nodeId: String): Boolean {
        val nodeInfo = getNodeInfoFromRedis(nodeId)
        
        if (nodeInfo == null) {
            logger.warn("Node $nodeId not found in Redis")
            return false
        }
        
        // 检查节点是否在活跃节点集合中
        val isInActiveNodes = redisTemplate.opsForSet().isMember(ACTIVE_NODES_KEY, nodeId) ?: false
        if (!isInActiveNodes) {
            logger.warn("Node $nodeId not in active nodes set")
            return false
        }
        
        val fiveMinutesAgo = LocalDateTime.now().minusMinutes(5)
        return nodeInfo.status == NodeStatus.ONLINE && 
               nodeInfo.lastHeartbeat.isAfter(fiveMinutesAgo)
    }

}