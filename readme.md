# Giggle 翻译系统设计文档

## 项目概述

Giggle 是一个基于微服务架构的智能翻译系统，支持语音转文字和多语言翻译功能。系统采用分布式架构，通过 Redis 消息队列实现服务间通信，支持水平扩展和高并发处理。

## 系统架构

### 整体架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   用户客户端     │◄──►│   API Gateway   │◄──►│   负载均衡器     │
│                 │    │  (Spring Boot)  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │                 │
                       │   Redis 集群    │
                       │  (消息队列/缓存) │
                       │                 │
                       └─────────────────┘
                                │
                                ▼
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│ Whisper Service │    │ Whisper Service │    │ Whisper Service │
│   (Python)      │    │   (Python)      │    │   (Python)      │
│   Node 1        │    │   Node 2        │    │   Node N        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                       ┌─────────────────┐
                       │                 │
                       │   MySQL 数据库  │
                       │  (持久化存储)   │
                       │                 │
                       └─────────────────┘
```

### 核心组件

#### 1. API Gateway (Spring Boot + Kotlin)
- **功能**: 统一入口，任务分发，状态管理
- **端口**: 8080
- **主要职责**:
  - 接收用户翻译请求
  - 任务创建和状态管理
  - 工作节点负载均衡
  - 结果聚合和返回

#### 2. Whisper Service (Python)
- **功能**: 语音转录和文本翻译
- **端口**: 8001+
- **主要职责**:
  - 语音转文字 (OpenAI Whisper)
  - 多语言翻译 (Google/Bing/OpenAI)
  - 任务执行和状态上报
  - 节点健康监控

#### 3. Redis 集群
- **功能**: 消息队列和缓存
- **端口**: 6379
- **主要职责**:
  - 任务队列管理
  - 节点状态同步
  - 实时通信中介

#### 4. MySQL 数据库
- **功能**: 持久化存储
- **端口**: 3306
- **主要职责**:
  - 任务记录存储
  - 节点信息管理
  - 翻译结果持久化

## 业务流程

### 翻译任务处理流程

```
用户提交任务
     │
     ▼
┌─────────────────┐
│ 1. API Gateway  │
│   接收请求      │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 2. 任务创建     │
│   - 生成任务ID  │
│   - 存储到MySQL │
│   - 状态: PENDING│
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 3. 节点选择     │
│   - 查询可用节点│
│   - 负载均衡    │
│   - 任务分配    │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 4. 任务推送     │
│   - 推送到Redis │
│   - 队列: task_ │
│     queue:{node}│
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 5. 节点处理     │
│   - 拉取任务    │
│   - 语音转录    │
│   - 文本翻译    │
│   - 状态更新    │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 6. 结果返回     │
│   - 上传结果    │
│   - 更新状态    │
│   - 通知完成    │
└─────────────────┘
```

### 节点管理流程

```
节点启动
     │
     ▼
┌─────────────────┐
│ 1. 节点注册      │
│   - 注册到Redis  │  
│   - 状态: ONLINE │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 2. 心跳循环      │
│   - 定期发送心跳  │
│   - 更新状态信息  │
│   - 资源使用情况  │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 3. 任务监听      │
│   - 监听任务队列  │
│   - 并发处理任务  │
│   - 状态上报      │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 4. 优雅关闭      │
│   - 完成当前任务  │
│   - 注销节点     │
│   - 清理资源     │
└─────────────────┘
```

## 数据模型

### 翻译任务表 (translation_tasks)

```sql
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
```

## Redis 通信协议

### 键命名规范

- **节点管理**:
  - `active_nodes`: SET - 活跃节点列表
  - `worker_nodes:{node_id}`: HASH - 节点详细信息
  - `node_rankings`: sorted set - 有序集合，根据资源和负载情况排序节点

- **任务管理**:
  - `task_queue:{node_id}`: LIST - 节点任务队列
  - `control_queue:{node_id}`: LIST - 控制信息，如取消任务

### 消息格式

#### 任务消息
```json
{
  "task_id": "task_123456",
  "type": "TRANSLATION",
  "audio_file_path": "/path/to/audio.mp3",
  "source_language": "auto",
  "target_languages": ["en", "zh-cn", "ja"],
  "origin_text": "xxxx",
  "created_at": "2024-01-15T10:30:00",
  "timeout": 60
}
```


### 高效打包方案 (SimplifiedTextPacker)

系统采用自研的高效二进制打包方案来存储和查询翻译结果，显著提升存储效率和查询性能。

#### 核心特性

- **压缩存储**: 使用 zlib 压缩算法，压缩率高达 70-90%
- **快速查询**: 基于哈希索引的 O(1) 查询复杂度
- **批量处理**: 支持多任务翻译结果的批量打包
- **多源支持**: 同时支持文本翻译和语音转录结果
- **跨语言兼容**: 完美支持多语言文本和特殊字符

#### 数据结构设计
文件结构:
```
┌─────────────────┐
│   文件头 (16B)   │  版本 + 语言数量 + 索引偏移
├─────────────────┤
│   语言表         │  语言代码存储
├─────────────────┤
│   语言索引       │  语言 -> 文本索引映射
├─────────────────┤
│   文本索引       │  任务ID + 偏移 + 长度 + 类型
├─────────────────┤
│   压缩文本数据    │  zlib 压缩的翻译内容
└─────────────────┘
```
#### 查询机制

支持通过 `语言 -> 任务ID -> 文本来源` 的三级索引快速定位翻译结果：

```python
# 查询示例
result = packer.query_text(
    packed_data=binary_data,
    language="zh",           # 目标语言
    task_id="task_123456",   # 任务ID
    source_type="TEXT"       # 文本来源: TEXT/AUDIO
)

```
#### 性能优势
- 存储效率 : 相比 JSON 格式节省 60-80% 存储空间
- 查询速度 : 毫秒级查询响应，支持高并发访问
- 内存友好 : 按需解压，避免全量加载
- 扩展性强 : 支持任意数量的语言和任务 应用场景
- 翻译结果的持久化存储
- 多语言内容的快速检索
- 大批量翻译任务的结果聚合
- 翻译缓存和结果复用

## API 接口设计

### 翻译任务接口

#### 创建翻译任务
```http
POST /api/tasks
Content-Type: multipart/form-data

{
  "textContent": "xxxx",
  "source_language": "auto",
  "target_languages": ["en", "zh-cn", "ja"]
}
```

#### 创建语音转文字且翻译任务
```http
POST /api/tasks/audio
Content-Type: multipart/form-data

{
  "file": "<binary>",
  "originalText": "xxxx",
  "source_language": "auto",
  "target_languages": ["en", "zh-cn", "ja"]
}
```

#### 查询任务状态
```http
GET /api/tasks/{task_id}

Response:
{
  "id": "8212a52d-acb7-43ab-92c4-c8915213272e",
  "sourceLanguage": "en",
  "targetLanguages": [
    "zh-cn",
    "zh-tw",
    "zh",
    "en",
    "en-us",
    "en-gb",
    "pt"
  ],
  "textContent": null,
  "audioFilePath": "/Users/chennan/cncode/giggle/apigateway/uploads/audio//8212a52d-acb7-43ab-92c4-c8915213272e.mp3",
  "status": "PROCESSING",
  "createdAt": "2025-06-21T09:43:12",
  "updatedAt": "2025-06-21T09:43:13",
  "assignedNodeId": "whisper-node-1",
  "resultFilePath": null,
  "errorMessage": null,
  "retryCount": 0
}
```

#### 取消任务
```http
DELETE /api/tasks/{task_id}/cancel

```

#### 查询文本
```http
GET /tasks/text?taskId=&language=&source=

```
### 节点管理接口

#### 获取节点列表
```http
GET /api/workers

Response:
{
  "nodes": [
    {
      "node_id": "whisper-node-1",
      "status": "ONLINE",
      "active_tasks": 2,
      "cpu_usage": 45.2,
      "memory_usage": 60.5,
      "gpu_available": true
    }
  ]
}
```

## 部署架构

### 开发环境
```bash
# 1. 启动基础服务
docker-compose up -d redis mysql

# 2. 启动 API Gateway
cd apigateway && ./gradlew bootRun

# 3. 启动 Whisper Service
cd whisper_service && python main.py
```



### 扩展部署
```bash
# 添加新节点
NODE_ID=whisper-node-4 python main.py
# 添加新节点
NODE_ID=whisper-node-5 python main.py
·
·
·
NODE_ID=whisper-node-6 python main.py
```

## 技术特性

### 高可用性
- **服务冗余**: 多个 Whisper Service 节点
- **故障转移**: 自动任务重分配
- **健康检查**: 定期心跳监控

### 可扩展性
- **水平扩展**: 动态添加工作节点
- **负载均衡**: 智能任务分配
- **资源监控**: CPU/GPU/内存使用率

### 性能优化
- **GPU 加速**: 支持 CUDA 加速推理
- **并发处理**: 每节点支持多任务并发
- **缓存机制**: Redis 缓存热点数据
- **高效打包**: 采用二进制打包方案优化翻译结果存储

