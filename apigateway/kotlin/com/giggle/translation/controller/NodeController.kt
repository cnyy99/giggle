package com.giggle.translation.controller

import com.giggle.translation.common.BaseController
import com.giggle.translation.common.BaseService
import com.giggle.translation.model.NodeInfo
import com.giggle.translation.service.NodeManagerService
import com.giggle.translation.service.TaskDispatchService
import org.springframework.data.redis.core.RedisTemplate
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api")
class NodeController(
    private val nodeManagerService: NodeManagerService,
    private val taskDispatchService: TaskDispatchService,
    private val redisTemplate: RedisTemplate<String, String>
) : BaseController(){
    
    @GetMapping("/nodes")
    fun getAllNodes(): ResponseEntity<List<NodeInfo>> {
        val nodes = nodeManagerService.getAllNodesAsNodeInfo()
        return ResponseEntity.ok(nodes)
    }
    
    @GetMapping("/nodes/available")
    fun getAvailableNodes(): ResponseEntity<List<NodeInfo>> {
        val nodes = nodeManagerService.getAvailableNodes()
        return ResponseEntity.ok(nodes)
    }
    
    @GetMapping("/rankings")
    fun getNodeRankings(): ResponseEntity<List<Map<String, Any>>> {
        val rankings = redisTemplate.opsForZSet().rangeWithScores("node_rankings", 0, -1)
        val result = rankings?.map { 
            mapOf(
                "nodeId" to (it.value as Any),
                "score" to (it.score as Any)
            )
        } ?: emptyList()
        return ResponseEntity.ok(result)
    }
    
    @GetMapping("/tasks/pending/count")
    fun getPendingTaskCount(): ResponseEntity<Map<String, Long>> {
        val count = taskDispatchService.getPendingTaskCount()
        return ResponseEntity.ok(mapOf("pendingCount" to count))
    }
    
    @GetMapping("/{nodeId}/health")
    fun checkNodeHealth(@PathVariable nodeId: String): ResponseEntity<Map<String, Boolean>> {
        val isHealthy = nodeManagerService.isNodeHealthy(nodeId)
        return ResponseEntity.ok(mapOf("healthy" to isHealthy))
    }

    
    @DeleteMapping("/{nodeId}/ranking")
    fun removeNodeFromRanking(@PathVariable nodeId: String): ResponseEntity<Void> {
        nodeManagerService.removeNodeFromRanking(nodeId)
        return ResponseEntity.ok().build()
    }
}