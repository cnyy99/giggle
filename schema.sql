-- 创建翻译数据库的表结构

-- 创建翻译任务表
CREATE TABLE `translation_tasks` (
  `id` varchar(255) NOT NULL,
  `status` enum('PENDING','DISPATCHING','PROCESSING','COMPLETED','FAILED','CANCELLED') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'PENDING',
  `audio_file_path` varchar(500) DEFAULT NULL,
  `text_content` text,
  `source_language` varchar(10) NOT NULL,
  `target_languages` varchar(500) NOT NULL,
  `assigned_node_id` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `result_file_path` varchar(500) DEFAULT NULL,
  `error_message` text,
  `retry_count` int NOT NULL DEFAULT '0',
  `original_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `accuracy` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_translation_tasks_status` (`status`),
  KEY `idx_translation_tasks_created_at` (`created_at`),
  KEY `idx_translation_tasks_assigned_node` (`assigned_node_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;