package com.giggle.translation.service

import com.giggle.translation.common.BaseService
import com.giggle.translation.dto.CreateTaskRequest
import com.giggle.translation.model.NodeInfo
import com.giggle.translation.model.TaskStatus
import com.giggle.translation.model.TranslationTask
import com.giggle.translation.model.TranslationTasks
import org.ktorm.database.Database
import org.ktorm.dsl.*
import org.ktorm.entity.*
import org.springframework.stereotype.Service
import org.springframework.web.multipart.MultipartFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.time.LocalDateTime
import java.util.*

@Service
class TranslationService(
    private val database: Database,
    private val nodeManagerService: NodeManagerService,
    private val taskDispatchService: TaskDispatchService
) : BaseService() {

     fun createTask(request: CreateTaskRequest): TranslationTask {
        val taskId = UUID.randomUUID().toString()
        val now = LocalDateTime.now()

        database.insert(TranslationTasks) {
            set(it.id, taskId)
            set(it.status, TaskStatus.PENDING)
            set(it.textContent, request.textContent)
            set(it.sourceLanguage, request.sourceLanguage)
            set(it.targetLanguages, request.targetLanguages)
            set(it.createdAt, now)
            set(it.updatedAt, now)
            set(it.retryCount, 0)
        }

        val task = database.sequenceOf(TranslationTasks)
            .find { it.id eq taskId }!!

        // 自动分发任务
        taskDispatchService.dispatchTask(task)

        return task
    }

     fun createAudioTask(
        file: MultipartFile,
        sourceLanguage: String,
        targetLanguages: List<String>,
        originalText: String?
    ): TranslationTask {
        val taskId = UUID.randomUUID().toString()
        val now = LocalDateTime.now()

        // 保存音频文件到存储
        val audioFilePath = saveAudioFile(file, taskId)

        database.insert(TranslationTasks) {
            set(it.id, taskId)
            set(it.status, TaskStatus.PENDING)
            set(it.audioFilePath, audioFilePath)
            set(it.originalText, originalText)
            set(it.sourceLanguage, sourceLanguage)
            set(it.targetLanguages, targetLanguages)
            set(it.createdAt, now)
            set(it.updatedAt, now)
            set(it.retryCount, 0)
        }

        val task = database.sequenceOf(TranslationTasks)
            .find { it.id eq taskId }!!

        // 自动分发任务
        taskDispatchService.dispatchTask(task)

        return task
    }

    private fun saveAudioFile(
        file: MultipartFile,
        taskId: String
    ): String {
        val uploadDir = "/Users/chennan/cncode/giggle/apigateway/uploads/audio/"
        val fileName = "$taskId.${file.originalFilename?.substringAfterLast('.') ?: "wav"}"
        val filePath = "$uploadDir/$fileName"

        try {
            // 创建目录
            val directory = java.io.File(uploadDir)
            if (!directory.exists()) {
                directory.mkdirs()
            }

            // 保存文件
            val targetFile = java.io.File(filePath)
            file.transferTo(targetFile)

            return filePath
        } catch (e: Exception) {
            throw RuntimeException("Failed to save audio file: ${e.message}", e)
        }
    }

     fun getTask(taskId: String): TranslationTask? {
        return database.sequenceOf(TranslationTasks)
            .find { it.id eq taskId }
    }

     fun cancelTask(taskId: String) {
        val task = getTask(taskId)
        if (task == null) {
            logger.warn("Task $taskId not found")
            return
        }

        // 更新数据库状态
        database.update(TranslationTasks) {
            set(it.status, TaskStatus.CANCELLED)
            set(it.updatedAt, LocalDateTime.now())
            where { it.id eq taskId }
        }

        // 如果任务已分配给节点，通知Python服务取消
        task.assignedNodeId?.let { nodeId ->
            notifyNodeToCancelTask(nodeId, taskId)
        }

        logger.info("Task $taskId cancelled successfully")
    }

    private fun notifyNodeToCancelTask(
        nodeId: String,
        taskId: String
    ) {
        try {
            taskDispatchService.cancelTask(taskId, nodeId)

            logger.info("Cancel notification sent to node $nodeId for task $taskId")
        } catch (e: Exception) {
            logger.error("Failed to notify node $nodeId to cancel task $taskId", e)
        }
    }
    

     fun queryText(
        taskId: String,
        language: String,
        source: String
    ): String? {
        try {
            // 获取任务的打包数据
            val task = getTask(taskId) ?: return null
            val packedData = getPackedData(task) ?: return null

            return queryTextFromPackedData(packedData, language, taskId, source)
        } catch (e: Exception) {
            logger.error("Failed to query text: ${e.message}", e)
            return null
        }
    }

    private fun getPackedData(task: TranslationTask): ByteArray? {
        // 从任务结果文件路径读取打包数据
        return task.resultFilePath?.let { path ->
            try {
                java.io.File(path).readBytes()
            } catch (e: Exception) {
                logger.error("Failed to read packed data from $path: ${e.message}", e)
                null
            }
        }
    }

    private fun queryTextFromPackedData(
        packedData: ByteArray,
        language: String,
        taskId: String,
        sourceType: String
    ): String? {
        try {
            val HEADER_SIZE = 16
            val TEXT_INDEX_ITEM_SIZE = 20

            if (packedData.size < HEADER_SIZE) {
                return null
            }

            // 解析文件头 (小端序)
            val buffer = ByteBuffer.wrap(packedData).order(ByteOrder.LITTLE_ENDIAN)
            val version = buffer.getInt(0)
            val langCount = buffer.getInt(4)
            val langIndexOffset = buffer.getInt(8)
            val textDataOffset = buffer.getInt(12)

            // 使用确定性hash算法，与Python版本保持一致
            val langHash = deterministicHash(language)

            // 查找语言索引
            var textIndexStart: Int? = null
            var textCount = 0

            for (i in 0 until langCount) {
                val pos = langIndexOffset + i * 12 // 语言索引项大小：4+4+4=12字节
                if (pos + 12 <= packedData.size) {
                    val storedHash = buffer.getInt(pos).toLong() and 0xFFFFFFFFL
                    val textOffset = buffer.getInt(pos + 4)
                    val count = buffer.getInt(pos + 8)

                    if (storedHash == langHash) {
                        textIndexStart = langIndexOffset + langCount * 12 + textOffset
                        textCount = count
                        break
                    }
                }
            }

            if (textIndexStart == null) {
                return null
            }

            // 准备查询参数
            val taskIdBytes = taskId.toByteArray(Charsets.UTF_8).take(8).toByteArray()
            val paddedTaskIdBytes = ByteArray(8)
            System.arraycopy(taskIdBytes, 0, paddedTaskIdBytes, 0, minOf(taskIdBytes.size, 8))

            // 验证源类型
            val sourceTypeCode = when (sourceType.uppercase()) {
                "TEXT" -> 0
                "AUDIO" -> 1
                else -> return null // 无效的源类型
            }

            // 查找文本索引
            for (i in 0 until textCount) {
                val pos = textIndexStart + i * TEXT_INDEX_ITEM_SIZE
                if (pos + TEXT_INDEX_ITEM_SIZE <= packedData.size) {
                    // 读取存储的task_id (8字节)
                    val storedTaskIdBytes = ByteArray(8)
                    System.arraycopy(packedData, pos, storedTaskIdBytes, 0, 8)

                    val dataOffset = buffer.getInt(pos + 8)
                    val dataLength = buffer.getInt(pos + 12)
                    val storedSourceType = buffer.getShort(pos + 16).toInt()

                    // 比较task_id和源类型
                    if (paddedTaskIdBytes.contentEquals(storedTaskIdBytes) &&
                        storedSourceType == sourceTypeCode
                    ) {

                        // 读取并解压缩文本数据
                        val textStart = textDataOffset + dataOffset
                        val textEnd = textStart + dataLength

                        if (textEnd <= packedData.size) {
                            val compressedData = packedData.sliceArray(textStart until textEnd)
                            val decompressedData = decompressData(compressedData)
                            return decompressedData?.toString(Charsets.UTF_8)
                        }
                    }
                }
            }

            return null

        } catch (e: Exception) {
            logger.error("Failed to query text from packed data: ${e.message}", e)
            return null
        }
    }

    // 添加确定性hash方法，与Python版本保持一致
    private fun deterministicHash(text: String): Long {
        return try {
            val md = java.security.MessageDigest.getInstance("MD5")
            val hashBytes = md.digest(text.toByteArray(Charsets.UTF_8))
            // 取前4个字节转换为无符号32位整数
            val hash = java.nio.ByteBuffer.wrap(hashBytes.sliceArray(0..3))
                .order(java.nio.ByteOrder.BIG_ENDIAN)
                .getInt()
            hash.toLong() and 0xFFFFFFFFL
        } catch (e: Exception) {
            logger.error("Failed to calculate deterministic hash: ${e.message}", e)
            0L
        }
    }

    private fun decompressData(compressedData: ByteArray): ByteArray? {
        return try {
            val inflater = java.util.zip.Inflater()
            inflater.setInput(compressedData)

            val buffer = ByteArray(1024)
            val output = java.io.ByteArrayOutputStream()

            while (!inflater.finished()) {
                val count = inflater.inflate(buffer)
                output.write(buffer, 0, count)
            }

            inflater.end()
            output.toByteArray()
        } catch (e: Exception) {
            logger.error("Failed to decompress data: ${e.message}", e)
            null
        }
    }

     fun getAllNodes(): List<NodeInfo> {
        return nodeManagerService.getAllNodesAsNodeInfo()
    }

     fun getAvailableNodes(): List<NodeInfo> {
        return nodeManagerService.getAvailableNodes()
    }

     fun queryTasks(
        status: TaskStatus?,
        sourceLanguage: String?,
        targetLanguage: String?,
        textQuery: String?,
        page: Int,
        size: Int
    ): List<TranslationTask> {
        var query = database.sequenceOf(TranslationTasks)

        status?.let {
            query = query.filter { task -> task.status eq it }
        }

        sourceLanguage?.let {
            query = query.filter { task -> task.sourceLanguage eq it }
        }

        targetLanguage?.let {
            query = query.filter { task -> task.targetLanguages like "%$it%" }
        }

        textQuery?.let { searchText ->
            query = query.filter { task ->
                (task.textContent like "%$searchText%") or (task.errorMessage like "%$searchText%")
            }
        }

        return query
            .drop(page * size)
            .take(size)
            .toList()
    }
}