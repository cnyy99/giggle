package com.giggle.translation.service

import com.giggle.translation.common.BaseService
import com.giggle.translation.model.NodeInfo
import com.giggle.translation.model.TaskStatus
import com.giggle.translation.model.TranslationTask
import com.giggle.translation.model.TranslationTasks
import com.giggle.translation.utils.DistributedLock
import com.giggle.translation.utils.JacksonUtil
import jakarta.annotation.PostConstruct
import jakarta.annotation.PreDestroy
import org.ktorm.database.Database
import org.ktorm.dsl.and
import org.ktorm.dsl.count
import org.ktorm.dsl.eq
import org.ktorm.dsl.from
import org.ktorm.dsl.less
import org.ktorm.dsl.map
import org.ktorm.dsl.select
import org.ktorm.dsl.update
import org.ktorm.dsl.where
import org.ktorm.entity.filter
import org.ktorm.entity.find
import org.ktorm.entity.sequenceOf
import org.ktorm.entity.toList
import org.springframework.data.redis.core.RedisTemplate
import org.springframework.stereotype.Service
import java.time.LocalDateTime
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

@Service
class TaskDispatchService(
    private val redisTemplate: RedisTemplate<String, String>,
    private val nodeManagerService: NodeManagerService,
    private val database: Database,
    private val distributedLock: DistributedLock
) : BaseService() {
    private val executor: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()

    companion object {
        private const val PENDING_TASKS_QUEUE = "pending_tasks"
        private const val MAX_RETRY_ATTEMPTS = 10
        private const val RETRY_INTERVAL_SECONDS = 30L
        private const val TASK_RECOVERY_INTERVAL_SECONDS = 300L // 5分钟检查一次
        private const val TASK_STUCK_THRESHOLD_MINUTES = 30L // 任务处理超过30分钟视为卡住
    }

    @PostConstruct
    fun startTaskDispatcher() {
        // 启动定时任务处理待分发的任务
        executor.scheduleWithFixedDelay({
            try {
                processPendingTasks()
            } catch (e: Exception) {
                logger.error("Error processing pending tasks", e)
            }
        }, 0, RETRY_INTERVAL_SECONDS, TimeUnit.SECONDS)

        // 启动定时任务检查卡住的任务
        executor.scheduleWithFixedDelay({
            try {
                recoverStuckTasks()
            } catch (e: Exception) {
                logger.error("Error recovering stuck tasks", e)
            }
        }, TASK_RECOVERY_INTERVAL_SECONDS, TASK_RECOVERY_INTERVAL_SECONDS, TimeUnit.SECONDS)

        logger.info("Task dispatcher started")
    }

    @PreDestroy
    fun stopTaskDispatcher() {
        executor.shutdown()
        try {
            if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                executor.shutdownNow()
            }
        } catch (e: InterruptedException) {
            executor.shutdownNow()
        }
        logger.info("Task dispatcher stopped")
    }

    fun dispatchTask(task: TranslationTask): Boolean {
        // 使用任务ID作为锁键，确保同一任务不会被重复分发
        val taskLockKey = "task_dispatch:${task.id}"

        return distributedLock.withLock(taskLockKey, expireTime = 10L, waitTime = 2L) {
            // 重新检查任务状态，防止重复分发
            val currentTask = database.sequenceOf(TranslationTasks).find { it.id eq task.id }

            if (currentTask?.status != TaskStatus.PENDING) {
                logger.info("Task ${task.id} is no longer pending, skipping dispatch")
                return@withLock true
            }

            currentTask.status == TaskStatus.DISPATCHING
            currentTask.updatedAt = LocalDateTime.now()
            currentTask.flushChanges()

            val availableNode = nodeManagerService.selectOptimalNode(task)

            if (availableNode != null) {
                dispatchToNodeWithLock(task, availableNode)
            } else {
                addToPendingQueue(task)
            }
        } ?: false
    }

    private fun dispatchToNodeWithLock(
        task: TranslationTask,
        node: NodeInfo
    ): Boolean {
        val nodeLockKey = "node_dispatch:${node.nodeId}"

        return distributedLock.withLock(nodeLockKey, expireTime = 5L, waitTime = 1L) {
            try {
                // 从数据库查询当前任务数量，而不是从Redis
                val currentTaskCount = database.from(TranslationTasks).select(count()).where {
                    (TranslationTasks.assignedNodeId eq node.nodeId) and (TranslationTasks.status eq TaskStatus.PROCESSING)
                }.map { it.getInt(1) }.first()

                if (currentTaskCount >= 10) {
                    logger.info("Node ${node.nodeId} is at capacity, cannot dispatch task ${task.id}")
                    return@withLock false
                }

                val taskMessage = TaskMessage(
                    taskId = task.id,
                    audioFilePath = task.audioFilePath,
                    textContent = task.textContent,
                    sourceLanguage = task.sourceLanguage,
                    targetLanguages = task.targetLanguages,
                    originalText = task.originalText
                )

                val messageJson = JacksonUtil.toJson(taskMessage)
                redisTemplate.opsForList().leftPush("task_queue:${node.nodeId}", messageJson)

                // 只更新任务状态到数据库，不更新Redis中的任务计数
                database.update(TranslationTasks) {
                    set(it.assignedNodeId, node.nodeId)
                    set(it.status, TaskStatus.PROCESSING)
                    set(it.updatedAt, LocalDateTime.now())
                    where { it.id eq task.id }
                }

                logger.info("Task ${task.id} dispatched to node ${node.nodeId}")
                true
            } catch (e: Exception) {
                logger.error("Failed to dispatch task ${task.id} to node ${node.nodeId}", e)
                false
            }
        } ?: false
    }

    private fun addToPendingQueue(task: TranslationTask): Boolean {
        return try {
            val pendingTaskInfo = mapOf(
                "taskId" to task.id, "retryCount" to "0", "addedAt" to LocalDateTime.now().toString()
            )

            val taskInfoJson = JacksonUtil.toJson(pendingTaskInfo)
            redisTemplate.opsForList().leftPush(PENDING_TASKS_QUEUE, taskInfoJson)

            logger.info("Task ${task.id} added to pending queue (no available nodes)")
            true
        } catch (e: Exception) {
            logger.error("Failed to add task ${task.id} to pending queue", e)
            false
        }
    }

    private fun processPendingTasks() {
        logger.info("Processing pending tasks")
        val pendingTaskJson = redisTemplate.opsForList().rightPop(PENDING_TASKS_QUEUE)
        if (pendingTaskJson != null) {
            try {
                val pendingTaskInfo = JacksonUtil.fromJson<Map<String, Any>>(pendingTaskJson)
                val taskId = pendingTaskInfo["taskId"] as String
                val retryCount = (pendingTaskInfo["retryCount"] as String).toInt()

                // 只保留任务级别的锁，防止同一任务被重复处理
                val taskProcessLockKey = "pending_task_process:$taskId"
                distributedLock.withLock(taskProcessLockKey, expireTime = 10L, waitTime = 5L) {
                    processSpecificPendingTask(taskId, retryCount)
                }
            } catch (e: Exception) {
                logger.error("Error processing pending task", e)
            }
        }
    }

    private fun processSpecificPendingTask(
        taskId: String,
        retryCount: Int
    ) {
        // 获取任务详情
        val task = database.sequenceOf(TranslationTasks).find { it.id eq taskId }

        if (task == null) {
            logger.warn("Pending task $taskId not found in database")
            return
        }

        // 检查任务状态，如果已经不是PENDING状态，跳过
        if (task.status != TaskStatus.PENDING) {
            logger.info("Task $taskId is no longer pending, skipping")
            return
        }

        // 尝试分发任务
        val availableNode = nodeManagerService.selectOptimalNode(task)
        if (availableNode != null) {
            val success = dispatchToNodeWithLock(task, availableNode)
            if (!success) {
                // 分发失败，重新加入队列
                requeuePendingTask(taskId, retryCount + 1)
            }
        } else {
            // 仍然没有可用节点
            if (retryCount < MAX_RETRY_ATTEMPTS) {
                // 重新加入队列等待下次重试
                requeuePendingTask(taskId, retryCount + 1)
                logger.debug("No available nodes for task $taskId, retry count: ${retryCount + 1}")
            } else {
                // 超过最大重试次数，标记任务失败
                database.update(TranslationTasks) {
                    set(it.status, TaskStatus.FAILED)
                    set(it.errorMessage, "No available nodes after $MAX_RETRY_ATTEMPTS retry attempts")
                    set(it.updatedAt, LocalDateTime.now())
                    where { it.id eq taskId }
                }
                logger.error("Task $taskId failed: exceeded maximum retry attempts")
            }
        }
    }

    private fun requeuePendingTask(
        taskId: String,
        retryCount: Int
    ) {
        try {
            val pendingTaskInfo = mapOf(
                "taskId" to taskId, "retryCount" to retryCount.toString(), "addedAt" to LocalDateTime.now().toString()
            )

            val taskInfoJson = JacksonUtil.toJson(pendingTaskInfo)
            redisTemplate.opsForList().leftPush(PENDING_TASKS_QUEUE, taskInfoJson)
        } catch (e: Exception) {
            logger.error("Failed to requeue pending task $taskId", e)
        }
    }

    fun dispatchToNode(
        task: TranslationTask,
        node: NodeInfo
    ): Boolean {
        return try {
            val taskMessage = TaskMessage(
                taskId = task.id,
                audioFilePath = task.audioFilePath,
                textContent = task.textContent,
                sourceLanguage = task.sourceLanguage,
                targetLanguages = task.targetLanguages,
                originalText = task.originalText
            )

            val taskJson = JacksonUtil.toJson(taskMessage)
            val queueKey = "task_queue:${node.nodeId}"

            redisTemplate.opsForList().leftPush(queueKey, taskJson)
            logger.info("Task ${task.id} dispatched to node ${node.nodeId}")

            true
        } catch (e: Exception) {
            logger.error("Failed to dispatch task ${task.id} to node ${node.nodeId}", e)
            false
        }
    }

    // 获取待处理任务数量（用于监控）
    fun getPendingTaskCount(): Long {
        return try {
            redisTemplate.opsForList().size(PENDING_TASKS_QUEUE) ?: 0L
        } catch (e: Exception) {
            logger.error("Failed to get pending task count", e)
            0L
        }
    }

    /**
     * 恢复卡住的任务
     * 检查长时间处于PROCESSING状态但未完成的任务，将它们重新标记为PENDING并重新分发
     */
    private fun recoverStuckTasks() {
        logger.info("recoverStuckTasks")

        val lockKey = "recover_stuck_tasks_lock"

        distributedLock.withLock(lockKey, expireTime = 60L, waitTime = 0L) {
            val stuckThresholdTime = LocalDateTime.now().minusMinutes(TASK_STUCK_THRESHOLD_MINUTES)

            // 查找所有卡住的任务（长时间处于PROCESSING状态）
            val stuckTasks = database.sequenceOf(TranslationTasks)
                .filter { (it.status eq TaskStatus.PROCESSING) and (it.updatedAt less stuckThresholdTime) }
                .toList()

            if (stuckTasks.isNotEmpty()) {
                logger.info("Found ${stuckTasks.size} stuck tasks to recover")

                stuckTasks.forEach { task ->
                    val taskLockKey = "task_recover:${task.id}"

                    distributedLock.withLock(taskLockKey, expireTime = 10L, waitTime = 1L) {
                        // 再次检查任务状态，确保它仍然需要恢复
                        val currentTask = database.sequenceOf(TranslationTasks).find { it.id eq task.id }

                        if (currentTask != null && currentTask.status == TaskStatus.PROCESSING && currentTask.updatedAt.isBefore(
                                stuckThresholdTime
                            )
                        ) {

                            // 增加重试计数
                            val newRetryCount = currentTask.retryCount + 1

                            if (newRetryCount <= MAX_RETRY_ATTEMPTS) {
                                // 更新任务状态为PENDING，准备重新分发
                                database.update(TranslationTasks) {
                                    set(it.status, TaskStatus.PENDING)
                                    set(it.assignedNodeId, null)
                                    set(it.retryCount, newRetryCount)
                                    set(it.updatedAt, LocalDateTime.now())
                                    where { it.id eq task.id }
                                }

                                logger.info("Recovered stuck task ${task.id}, retry count: $newRetryCount")

                                // 将任务添加到待处理队列
                                addToPendingQueue(currentTask)
                            } else {
                                // 超过最大重试次数，标记为失败
                                database.update(TranslationTasks) {
                                    set(it.status, TaskStatus.FAILED)
                                    set(it.errorMessage, "Task failed after $MAX_RETRY_ATTEMPTS recovery attempts")
                                    set(it.updatedAt, LocalDateTime.now())
                                    where { it.id eq task.id }
                                }

                                logger.error("Task ${task.id} failed: exceeded maximum recovery attempts")
                            }
                        }
                    }
                }
            }
        }
    }

    /**
     * 取消指定任务
     */
    fun cancelTask(
        taskId: String,
        nodeId: String
    ): Boolean {
        return try {
            val cancelMessage = mapOf(
                "action" to "CANCEL_TASK", "taskId" to taskId, "timestamp" to LocalDateTime.now().toString()
            )

            val messageJson = JacksonUtil.toJson(cancelMessage)
            redisTemplate.opsForList().leftPush("control_queue:$nodeId", messageJson)

            logger.info("Cancel message sent to node $nodeId for task $taskId")
            true
        } catch (e: Exception) {
            logger.error("Failed to send cancel message to node $nodeId for task $taskId", e)
            false
        }
    }
}

data class TaskMessage(
    val taskId: String,
    val audioFilePath: String?,
    val textContent: String?,
    val sourceLanguage: String,
    val targetLanguages: List<String>,
    val originalText: String?
)

