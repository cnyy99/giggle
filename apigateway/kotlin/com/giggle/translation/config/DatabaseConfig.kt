package com.giggle.translation.config

import org.ktorm.database.Database
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

@Configuration
class DatabaseConfig {
    
    @Value("\${spring.datasource.url}")
    private lateinit var url: String
    
    @Value("\${spring.datasource.username}")
    private lateinit var username: String
    
    @Value("\${spring.datasource.password}")
    private lateinit var password: String
    
    @Bean
    fun database(): Database {
        return Database.connect(
            url = url,
            user = username,
            password = password
        )
    }
}