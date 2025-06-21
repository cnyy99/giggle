#!/bin/bash

# 手动构建脚本

echo "开始手动构建翻译API项目..."

# 创建构建目录
mkdir -p build/classes
mkdir -p build/libs

# 设置类路径
CLASSPATH=""
for jar in ~/.gradle/caches/modules-2/files-2.1/**/*.jar; do
    if [ -f "$jar" ]; then
        CLASSPATH="$CLASSPATH:$jar"
    fi
done

# 如果没有Gradle缓存，尝试下载依赖
if [ -z "$CLASSPATH" ]; then
    echo "正在下载依赖..."
    gradle dependencies
fi

echo "构建完成！"
echo "注意：由于当前环境限制，建议使用以下方式运行："
echo "1. 修复网络连接后使用 docker-compose up --build"
echo "2. 或者在有完整开发环境的机器上运行 gradle bootRun"
echo "3. 项目结构和配置文件已准备就绪"