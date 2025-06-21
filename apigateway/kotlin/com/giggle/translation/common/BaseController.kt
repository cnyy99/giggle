package com.giggle.translation.common

import jakarta.servlet.http.HttpServletRequest
import org.slf4j.Logger
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.stereotype.Component
import kotlin.properties.ReadOnlyProperty
import kotlin.reflect.KProperty
import kotlin.reflect.full.companionObject

fun getLogger(forClass: Class<*>): Logger =
    LoggerFactory.getLogger(forClass)

inline fun <T : Any> getClassForLogging(javaClass: Class<T>): Class<*> {
    return javaClass.enclosingClass?.takeIf {
        it.kotlin.companionObject?.java == javaClass
    } ?: javaClass
}


class LoggerDelegate<in R : Any> : ReadOnlyProperty<R, Logger> {
    override fun getValue(
        thisRef: R,
        property: KProperty<*>
    ) = getLogger(getClassForLogging(thisRef.javaClass))
}

open class LoggerAsPropertyDelegate {
    protected val logger by LoggerDelegate()
}

@Component
class BaseController : LoggerAsPropertyDelegate() {


    @Autowired
    internal final lateinit var request: HttpServletRequest


}

typealias BaseService = BaseController