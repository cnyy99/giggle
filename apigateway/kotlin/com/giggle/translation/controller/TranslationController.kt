package com.giggle.translation.controller

import com.giggle.translation.common.BaseController
import com.giggle.translation.dto.*
import com.giggle.translation.service.TranslationService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

@RestController
@RequestMapping("/api/v1/translation")
class TranslationController(
    private val translationService: TranslationService
) : BaseController() {

    @PostMapping("/tasks")
    fun createTask(@RequestBody request: CreateTaskRequest): ResponseEntity<TaskResponse> {
        val task = translationService.createTask(request)
        return ResponseEntity.ok(TaskResponse.from(task))
    }

    @PostMapping("/tasks/audio")
    fun createAudioTask(
        @RequestParam("file") file: MultipartFile,
        @RequestParam("sourceLanguage") sourceLanguage: String,
        @RequestParam("targetLanguages") targetLanguages: List<String>,
        @RequestParam("originalText", required = false) originalText: String?
    ): ResponseEntity<TaskResponse> {
        val task = translationService.createAudioTask(file, sourceLanguage, targetLanguages, originalText)
        return ResponseEntity.ok(TaskResponse.from(task))
    }

    @GetMapping("/tasks/{taskId}")
    fun getTask(@PathVariable taskId: String): ResponseEntity<TaskResponse> {
        val task = translationService.getTask(taskId)
        return if (task != null) {
            ResponseEntity.ok(TaskResponse.from(task))
        } else {
            ResponseEntity.notFound().build()
        }
    }

    @DeleteMapping("/tasks/{taskId}/cancel")
    fun cancelTask(@PathVariable taskId: String): ResponseEntity<Void> {
        translationService.cancelTask(taskId)
        return ResponseEntity.ok().build()
    }


    @GetMapping("/tasks/text")
    fun queryText(
        @RequestParam taskId: String,
        @RequestParam language: String,
        @RequestParam source: SourceType
    ): ResponseEntity<String> {
        val text = translationService.queryText(taskId, language, source.value)
        if (text == null) {
            logger.warn("Could not find text for task $taskId")
        }
        return if (text != null) {
            ResponseEntity.ok(text)
        } else {
            ResponseEntity.notFound().build()
        }
    }
}