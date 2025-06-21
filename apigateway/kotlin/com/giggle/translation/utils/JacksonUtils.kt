package com.giggle.translation.utils

import com.fasterxml.jackson.annotation.JsonInclude
import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.DeserializationFeature
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.SerializationFeature
import com.fasterxml.jackson.databind.node.ObjectNode
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule
import com.fasterxml.jackson.datatype.jsr310.deser.LocalDateDeserializer
import com.fasterxml.jackson.datatype.jsr310.deser.LocalDateTimeDeserializer
import com.fasterxml.jackson.datatype.jsr310.deser.LocalTimeDeserializer
import com.fasterxml.jackson.datatype.jsr310.ser.LocalDateSerializer
import com.fasterxml.jackson.datatype.jsr310.ser.LocalDateTimeSerializer
import com.fasterxml.jackson.datatype.jsr310.ser.LocalTimeSerializer
import com.fasterxml.jackson.module.kotlin.KotlinModule
import com.fasterxml.jackson.module.kotlin.convertValue
import com.fasterxml.jackson.module.kotlin.readValue
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule
import org.ktorm.jackson.KtormModule
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter


/**
 *
 *
 * @author chennan@kuaishou.com
 * @date 2022/9/4 15:36
 */


object JacksonUtil {
    private const val DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss.SSS"
    private const val DATE_FORMAT = "yyyy-MM-dd HH:mm:ss"
    private const val TIME_FORMAT = "HH:mm:ss.SSS"

    // creat new objectNode when access newObjectNode
    val newObjectNode: ObjectNode get() = jacksonMapper.createObjectNode()

    val jacksonMapper = ObjectMapper().apply {
        registerModule(KtormModule())
        registerModule(KotlinModule())
        registerModule(ParameterNamesModule())
        disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
        disable(SerializationFeature.FAIL_ON_EMPTY_BEANS)
        val javaTimeModule = JavaTimeModule().apply {
            addSerializer(
                LocalDateTime::class.java, LocalDateTimeSerializer(DateTimeFormatter.ofPattern(DATE_TIME_FORMAT))
            )
            addSerializer(
                LocalDate::class.java, LocalDateSerializer(DateTimeFormatter.ofPattern(DATE_FORMAT))
            )
            addSerializer(
                LocalTime::class.java, LocalTimeSerializer(DateTimeFormatter.ofPattern(TIME_FORMAT))
            )
            addDeserializer(
                LocalDateTime::class.java, LocalDateTimeDeserializer(DateTimeFormatter.ofPattern(DATE_TIME_FORMAT))
            )
            addDeserializer(
                LocalDate::class.java, LocalDateDeserializer(DateTimeFormatter.ofPattern(DATE_FORMAT))
            )
            addDeserializer(
                LocalTime::class.java, LocalTimeDeserializer(DateTimeFormatter.ofPattern(TIME_FORMAT))
            )
        }

        registerModule(javaTimeModule)
        setSerializationInclusion(JsonInclude.Include.ALWAYS)
        configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
    }

    fun toJson(obj: Any?): String = jacksonMapper.writeValueAsString(obj)

    private val prettyWriter = jacksonMapper.writerWithDefaultPrettyPrinter()

    fun toJsonPretty(obj: Any?): String = prettyWriter.writeValueAsString(obj);

    inline fun <reified T> convertValue(from: Any): T = jacksonMapper.convertValue(from)

    inline fun <reified T> fromJson(json: String): T = jacksonMapper.readValue(json)

    fun <T> fromJson(
        file: File,
        typeRef: TypeReference<T>
    ): T = jacksonMapper.readValue(file, typeRef)

    fun toObjectNode(obj: Any): ObjectNode =
        if (obj is String) jacksonMapper.readValue(obj) else jacksonMapper.valueToTree(obj)

    internal fun Any.toObjectNode(): ObjectNode =
        if (this is String) jacksonMapper.readValue(this) else jacksonMapper.valueToTree(this)

    fun toJsonNode(obj: Any): JsonNode =
        if (obj is String) jacksonMapper.readTree(obj) else jacksonMapper.valueToTree(obj)

    internal fun Any.toJsonNode(): JsonNode =
        if (this is String) jacksonMapper.readTree(this) else jacksonMapper.valueToTree(this)

}