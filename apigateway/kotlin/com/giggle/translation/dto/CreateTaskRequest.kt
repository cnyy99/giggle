package com.giggle.translation.dto

data class CreateTaskRequest(
    val sourceLanguage: String,
    val targetLanguages: List<String>,
    val textContent: String
)