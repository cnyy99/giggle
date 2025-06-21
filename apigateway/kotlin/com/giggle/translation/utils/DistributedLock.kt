package com.giggle.translation.utils

import org.slf4j.LoggerFactory
import org.springframework.data.redis.core.RedisTemplate
import org.springframework.stereotype.Component
import java.time.Duration
import java.util.concurrent.TimeUnit

@Component
class DistributedLock(
    private val redisTemplate: RedisTemplate<String, String>
) {
    private val logger = LoggerFactory.getLogger(DistributedLock::class.java)
    
    companion object {
        private const val LOCK_PREFIX = "lock:"
        private const val DEFAULT_EXPIRE_TIME = 30L // 秒
        private const val DEFAULT_WAIT_TIME = 5L // 秒
    }
    
    /**
     * 获取细粒度锁
     * @param lockKey 锁的键，应该是具体的资源标识
     * @param expireTime 锁过期时间（秒）
     * @param waitTime 等待锁的最大时间（秒）
     */
    fun tryLock(
        lockKey: String, 
        expireTime: Long = DEFAULT_EXPIRE_TIME,
        waitTime: Long = DEFAULT_WAIT_TIME
    ): Boolean {
        val key = "$LOCK_PREFIX$lockKey"
        val value = "${System.currentTimeMillis()}_${Thread.currentThread().id}"
        val endTime = System.currentTimeMillis() + waitTime * 1000
        
        while (System.currentTimeMillis() < endTime) {
            val success = redisTemplate.opsForValue().setIfAbsent(key, value, Duration.ofSeconds(expireTime))
            if (success == true) {
                logger.debug("Acquired lock: $lockKey")
                return true
            }
            
            // 短暂等待后重试
            try {
                Thread.sleep(50)
            } catch (e: InterruptedException) {
                Thread.currentThread().interrupt()
                return false
            }
        }
        
        logger.debug("Failed to acquire lock: $lockKey")
        return false
    }
    
    /**
     * 释放锁
     */
    fun unlock(lockKey: String): Boolean {
        val key = "$LOCK_PREFIX$lockKey"
        return try {
            redisTemplate.delete(key)
            logger.debug("Released lock: $lockKey")
            true
        } catch (e: Exception) {
            logger.error("Failed to release lock: $lockKey", e)
            false
        }
    }
    
    /**
     * 使用锁执行操作
     */
    fun <T> withLock(
        lockKey: String,
        expireTime: Long = DEFAULT_EXPIRE_TIME,
        waitTime: Long = DEFAULT_WAIT_TIME,
        operation: () -> T
    ): T? {
        return if (tryLock(lockKey, expireTime, waitTime)) {
            try {
                operation()
            } finally {
                unlock(lockKey)
            }
        } else {
            null
        }
    }
}