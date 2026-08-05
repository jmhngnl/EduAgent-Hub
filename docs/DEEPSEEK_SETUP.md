# DeepSeek 接入说明

## 两类 API Key 不要混用

- `API_KEYS`：EduAgent Hub 自己的访问密钥。前端“后端连接设置”中的
  `X-API-Key` 填这里的值。
- `LLM_API_KEY`：模型提供商密钥，只能写在服务器 `.env` 中，不能粘贴到
  浏览器或提交到 Git。

正确调用链：

```text
Browser -> EduAgent Hub FastAPI -> LangGraph -> DeepSeek API
```

前端的 API Base 必须指向 EduAgent Hub 后端，例如：

```text
http://192.168.150.101:8000
```

不能填写 `https://api.deepseek.com`。

## 推荐配置

```bash
cp .env.deepseek.example .env
vi .env
```

至少修改：

```env
API_KEYS=demo
API_KEY_WORKSPACES=demo:demo
MOCK_LLM=false
LLM_PROVIDER=deepseek
LLM_API_KEY=<your-deepseek-key>
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_THINKING_ENABLED=false
MOCK_EMBEDDINGS=true
CORS_ORIGINS=http://192.168.150.101:5173
```

重新创建 API 和 Worker 容器，使新的环境变量生效：

```bash
docker-compose up -d --build --force-recreate api worker frontend
```

检查后端安全状态（不会返回任何密钥）：

```bash
curl http://127.0.0.1:8000/v1/platform/status
```

浏览器连接设置填写：

```text
EduAgent API Base: http://192.168.150.101:8000
项目访问密钥: demo
```
