package com.giggle.translation.dto

import com.giggle.translation.model.TranslationTask
import com.giggle.translation.model.TaskStatus
import java.time.LocalDateTime

data class TaskResponse(
    val id: String,
    val sourceLanguage: String,
    val targetLanguages: List<String>,
    val textContent: String?,
    val audioFilePath: String?,
    val status: TaskStatus,
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime,
    val assignedNodeId: String?,
    val resultFilePath: String?,
    val errorMessage: String?,
    val originalText: String?,
    val retryCount: Int,
) {
    companion object {
        fun from(task: TranslationTask): TaskResponse {
            return TaskResponse(
                id = task.id,
                sourceLanguage = task.sourceLanguage,
                targetLanguages = task.targetLanguages,
                textContent = task.textContent,
                audioFilePath = task.audioFilePath,
                status = task.status,
                createdAt = task.createdAt,
                updatedAt = task.updatedAt,
                assignedNodeId = task.assignedNodeId,
                resultFilePath = task.resultFilePath,
                errorMessage = task.errorMessage,
                retryCount = task.retryCount,
                originalText = task.originalText
            )
        }
    }
}