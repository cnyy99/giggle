package com.giggle.translation

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication
import org.springframework.scheduling.annotation.EnableScheduling

@SpringBootApplication
@EnableScheduling
class TranslationApplication

fun main(args: Array<String>) {
    runApplication<TranslationApplication>(*args)
}