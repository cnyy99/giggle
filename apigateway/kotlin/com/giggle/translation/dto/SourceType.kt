package com.giggle.translation.dto

enum class SourceType(val value: String) {
    TEXT("TEXT"),
    AUDIO("AUDIO");
    
    companion object {
        fun fromString(value: String): SourceType? {
            return values().find { it.value.equals(value, ignoreCase = true) }
        }
    }
}