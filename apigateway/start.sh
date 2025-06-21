#!/bin/bash

# 翻译API网关启动脚本

echo "正在启动翻译API网关服务..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker未安装，请先安装Docker"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: docker-compose未安装，请先安装docker-compose"
    exit 1
fi

# 停止现有容器
echo "停止现有容器..."
docker-compose down

# 构建并启动服务
echo "构建并启动服务..."
docker-compose up --build -d

# 等待服务启动
echo "等待服务启动..."
sleep 30

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

# 显示日志
echo "显示应用日志..."
docker-compose logs app

echo "翻译API网关已启动！"
echo "API地址: http://localhost:8080"
echo "查看日志: docker-compose logs -f app"
echo "停止服务: docker-compose down"