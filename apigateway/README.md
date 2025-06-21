# 翻译API网关

这是一个基于Spring Boot和Kotlin开发的翻译服务API网关。

## 项目结构

```
apigateway/
├── kotlin/                    # Kotlin源代码
│   └── com/giggle/translation/
│       ├── TranslationApplication.kt    # 主应用类
│       ├── controller/                  # 控制器层
│       ├── dto/                        # 数据传输对象
│       ├── model/                      # 数据模型
│       ├── service/                    # 服务层
│       └── config/                     # 配置类
├── resources/
│   └── application.yml        # 应用配置
├── build.gradle.kts          # Gradle构建脚本
├── Dockerfile               # Docker镜像构建文件
├── docker-compose.yml       # Docker Compose配置
├── start.sh                # 启动脚本
└── build.sh                # 手动构建脚本
```

## 功能特性

- **翻译任务管理**: 创建、查询、更新翻译任务
- **多语言支持**: 支持中文、英文、日文、韩文、法文、德文、西班牙文
- **工作节点管理**: 管理翻译工作节点的状态和资源
- **异步处理**: 支持异步翻译任务处理
- **Redis缓存**: 使用Redis进行缓存和任务队列
- **MySQL存储**: 使用MySQL存储翻译任务和结果

## API接口

### 翻译任务接口

- `POST /api/tasks` - 创建翻译任务
- `GET /api/tasks/{id}` - 获取翻译任务详情
- `GET /api/tasks` - 获取翻译任务列表
- `PUT /api/tasks/{id}/status` - 更新任务状态

### 工作节点接口

- `GET /api/workers` - 获取工作节点列表
- `POST /api/workers/{id}/heartbeat` - 工作节点心跳

## 部署方式

### 方式1: Docker Compose (推荐)

```bash
# 启动所有服务
./start.sh

# 或者手动启动
docker-compose up --build -d
```

### 方式2: 本地运行

```bash
# 确保MySQL和Redis已启动
# 修改application.yml中的数据库连接配置
gradle bootRun
```

## 环境要求

- Java 17+
- Kotlin 1.9.20+
- MySQL 8.0+
- Redis 7.0+
- Docker & Docker Compose (可选)

## 配置说明

### 数据库配置

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/translation_db
    username: ${DB_USERNAME:root}
    password: ${DB_PASSWORD:password}
```

### Redis配置

```yaml
spring:
  redis:
    host: ${REDIS_HOST:localhost}
    port: ${REDIS_PORT:6379}
    password: ${REDIS_PASSWORD:}
```

## 已知问题

1. **Gradle构建问题**: 当前环境中Gradle构建可能失败，建议使用Docker方式部署
2. **网络连接**: Docker镜像下载可能因网络问题失败，请确保网络连接正常
3. **依赖版本**: 项目使用了较新的Spring Boot 3.2.0，确保Java版本兼容

## 故障排除

### 构建失败

```bash
# 清理构建缓存
gradle clean

# 跳过测试构建
gradle build -x test
```

### Docker问题

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs app

# 重新构建
docker-compose down
docker-compose up --build
```

## 开发说明

项目采用标准的Spring Boot项目结构，使用Ktorm作为ORM框架，支持MySQL数据库操作。所有的Kotlin文件都已正确配置包声明，项目结构清晰，便于维护和扩展。

## 联系方式

如有问题，请联系开发团队。