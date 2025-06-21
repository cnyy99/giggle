package com.giggle.translation.model

import org.ktorm.entity.Entity
import org.ktorm.schema.*
import java.time.LocalDateTime

interface TranslationTask : Entity<TranslationTask> {
    companion object : Entity.Factory<TranslationTask>()

    val id: String
    var status: TaskStatus
    var audioFilePath: String?
    var textContent: String?
    var sourceLanguage: String
    var targetLanguages: List<String>
    var assignedNodeId: String?
    var createdAt: LocalDateTime
    var updatedAt: LocalDateTime
    var resultFilePath: String?
    var errorMessage: String?
    var originalText: String?
    var retryCount: Int
    var accuracy: Double
}

enum class TaskStatus {
    PENDING, DISPATCHING, PROCESSING, COMPLETED, FAILED, CANCELLED
}

object TranslationTasks : Table<TranslationTask>("translation_tasks") {
    val id = varchar("id").primaryKey().bindTo { it.id }
    val status = enum<TaskStatus>("status").bindTo { it.status }
    val audioFilePath = varchar("audio_file_path").bindTo { it.audioFilePath }
    val textContent = text("text_content").bindTo { it.textContent }
    val sourceLanguage = varchar("source_language").bindTo { it.sourceLanguage }
    val targetLanguages = varchar("target_languages").transform(
        fromUnderlyingValue = { it.split(",") },
        toUnderlyingValue = { it.joinToString(",") }
    ).bindTo { it.targetLanguages }
    val assignedNodeId = varchar("assigned_node_id").bindTo { it.assignedNodeId }
    val accuracy = double("accuracy").bindTo { it.accuracy }
    val createdAt = datetime("created_at").bindTo { it.createdAt }
    val updatedAt = datetime("updated_at").bindTo { it.updatedAt }
    val resultFilePath = varchar("result_file_path").bindTo { it.resultFilePath }
    val errorMessage = text("error_message").bindTo { it.errorMessage }
    val originalText = text("original_text").bindTo { it.originalText }
    val retryCount = int("retry_count").bindTo { it.retryCount }
}