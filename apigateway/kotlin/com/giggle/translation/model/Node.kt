package com.giggle.translation.model

import java.time.LocalDateTime


enum class NodeStatus {
    ONLINE, OFFLINE, BUSY, MAINTENANCE
}

// 独立的节点信息数据类，用于API返回
data class NodeInfo(
    val nodeId: String,
    val host: String,
    val port: Int,
    val memoryTotal: Long,
    val memoryUsed: Long,
    val cpuUsage: Double,
    val gpuAvailable: Boolean,
    val status: NodeStatus,
    val lastHeartbeat: LocalDateTime,
    val activeTaskCount: Int
) {
    val memoryUsagePercent: Double
        get() = (memoryUsed.toDouble() / memoryTotal) * 100

    val availableMemory: Long
        get() = memoryTotal - memoryUsed
}
