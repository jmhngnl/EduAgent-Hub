# v1.1.0 升级说明

本次修复前端将模型服务地址误当作 EduAgent 后端地址的问题，并将 Chat 与
Embedding 配置解耦。

## 1. 应用补丁

在项目根目录执行：

```bash
git apply EduAgent-Hub-v1.1.0.patch
```

## 2. 修改服务器 `.env`

不要覆盖已有 `.env`，只需核对以下字段：

```env
API_KEYS=demo
API_KEY_WORKSPACES=demo:demo

MOCK_LLM=false
LLM_PROVIDER=deepseek
LLM_API_KEY=<new-deepseek-api-key>
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_THINKING_ENABLED=false

MOCK_EMBEDDINGS=true
OTEL_EXPORTER_OTLP_ENDPOINT=
CORS_ORIGINS=http://192.168.150.101:5173
```

由于模型 Key 曾出现在截图和上传包中，应在模型平台废弃旧 Key 并创建新 Key。

## 3. 重新构建

```bash
docker-compose up -d --build --force-recreate api worker frontend
```

PostgreSQL 和 Redis 不再映射到宿主机 5432/6379，容器内部通信不受影响。

## 4. 验证

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/platform/status
```

浏览器连接设置填写：

```text
EduAgent API Base: http://192.168.150.101:8000
项目访问密钥: demo
```

不要在浏览器填写 `https://api.deepseek.com` 或 DeepSeek 的 `sk-...` Key。

## 5. 提交并推送

```bash
git add .
git commit -m "fix: separate backend access and model provider configuration"
git push origin main
```
