import "./style.css";

type Citation = {
  document_id: string;
  source: string;
  chunk_id: string;
  score: number;
};

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing #app element");
};

const defaultApiBase = "http://localhost:8000";
const apiBase = localStorage.getItem("eduagentApiBase") ?? defaultApiBase;
const apiKey = localStorage.getItem("eduagentApiKey") ?? "";


/**
 * 创建会话ID
 *
 * crypto.randomUUID:
 * - HTTPS环境支持
 * - localhost支持
 *
 * HTTP + 局域网IP环境不支持，因此增加fallback
 */
function createSessionId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random()
    .toString(36)
    .substring(2, 15)}`;
}


const sessionId =
  localStorage.getItem("eduagentSessionId") ?? createSessionId();

localStorage.setItem("eduagentSessionId", sessionId);

app.innerHTML = `
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">LANGGRAPH · RAG · MCP · FASTAPI</p>
        <h1>EduAgent Hub</h1>
        <p class="subtitle">教育知识库与工作流智能体平台</p>
      </div>
      <div class="status" id="health">正在检查服务...</div>
    </header>

    <section class="grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <h2>知识库入库</h2>
            <p>粘贴教学制度、课程资料或实验室文档。</p>
          </div>
        </div>

        <label>
          文档 ID
          <input id="documentId" value="demo-policy" />
        </label>
        <label>
          来源
          <input id="source" value="教学管理制度.md" />
        </label>
        <label>
          文档内容
          <textarea id="documentText" rows="12">实验室算力资源申请流程：学生提交用途、预计 GPU 时长和数据合规说明，经导师审批后由管理员分配资源。涉及患者数据的任务必须完成脱敏，不得上传到未经批准的外部服务。</textarea>
        </label>
        <button id="ingestButton">切分并建立索引</button>
        <pre class="result" id="ingestResult">等待操作</pre>
      </article>

      <article class="panel chat-panel">
        <div class="panel-head">
          <div>
            <h2>Agent 对话</h2>
            <p>支持知识检索、工具调用、引用与 SSE 输出。</p>
          </div>
          <button class="ghost" id="settingsButton">连接设置</button>
        </div>

        <div class="messages" id="messages">
          <div class="message assistant">
            <strong>EduAgent</strong>
            <p>请先建立知识索引，然后询问制度、流程或计算问题。</p>
          </div>
        </div>

        <div class="composer">
          <textarea id="question" rows="3" placeholder="例如：申请 GPU 需要哪些材料？"></textarea>
          <button id="sendButton">发送</button>
        </div>

        <div class="citations" id="citations"></div>
      </article>
    </section>
  </main>

  <dialog id="settingsDialog">
    <form method="dialog" class="settings-form">
      <h2>连接设置</h2>
      <label>
        API Base
        <input id="apiBaseInput" value="${escapeHtml(apiBase)}" />
      </label>
      <label>
        X-API-Key
        <input id="apiKeyInput" type="password" value="${escapeHtml(apiKey)}" />
      </label>
      <div class="dialog-actions">
        <button value="cancel" class="ghost">取消</button>
        <button value="save" id="saveSettings">保存</button>
      </div>
    </form>
  </dialog>
`;

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[char] ?? char,
  );
}

function headers(contentType = true): HeadersInit {
  const result: Record<string, string> = {};
  if (contentType) {
    result["Content-Type"] = "application/json";
  }
  const savedKey = localStorage.getItem("eduagentApiKey");
  if (savedKey) {
    result["X-API-Key"] = savedKey;
  }
  return result;
}

function currentBase(): string {
  return (
    localStorage.getItem("eduagentApiBase") ?? defaultApiBase
  ).replace(/\/$/, "");
}

function addMessage(role: "user" | "assistant", content: string): HTMLElement {
  const container = document.querySelector<HTMLDivElement>("#messages");
  if (!container) throw new Error("Missing messages container");

  const element = document.createElement("div");
  element.className = `message ${role}`;
  element.innerHTML = `
    <strong>${role === "user" ? "你" : "EduAgent"}</strong>
    <p>${escapeHtml(content)}</p>
  `;
  container.appendChild(element);
  container.scrollTop = container.scrollHeight;
  return element;
}

function renderCitations(items: Citation[]): void {
  const container = document.querySelector<HTMLDivElement>("#citations");
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = `
    <h3>检索引用</h3>
    ${items
      .map(
        (item, index) => `
          <div class="citation">
            <span>[来源${index + 1}]</span>
            <strong>${escapeHtml(item.source)}</strong>
            <small>${escapeHtml(item.document_id)} · ${item.score.toFixed(4)}</small>
          </div>
        `,
      )
      .join("")}
  `;
}

async function checkHealth(): Promise<void> {
  const target = document.querySelector<HTMLDivElement>("#health");
  if (!target) return;
  try {
    const response = await fetch(`${currentBase()}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    target.textContent = `${data.status} · DB ${data.database} · Redis ${data.redis}`;
    target.classList.add(data.status === "ok" ? "ok" : "warn");
  } catch (error) {
    target.textContent = `服务不可用：${String(error)}`;
    target.classList.add("error");
  }
}

async function ingestText(): Promise<void> {
  const documentId =
    document.querySelector<HTMLInputElement>("#documentId")?.value.trim() ?? "";
  const source =
    document.querySelector<HTMLInputElement>("#source")?.value.trim() ?? "";
  const text =
    document.querySelector<HTMLTextAreaElement>("#documentText")?.value.trim() ??
    "";
  const result = document.querySelector<HTMLPreElement>("#ingestResult");
  const button = document.querySelector<HTMLButtonElement>("#ingestButton");
  if (!result || !button) return;

  button.disabled = true;
  result.textContent = "正在切分、向量化并写入索引...";
  try {
    const response = await fetch(`${currentBase()}/v1/knowledge/text`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        workspace_id: "demo",
        document_id: documentId,
        source,
        text,
        metadata: { source_type: "manual-demo" },
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(JSON.stringify(payload));
    }
    result.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    result.textContent = `入库失败：${String(error)}`;
  } finally {
    button.disabled = false;
  }
}

async function sendMessage(): Promise<void> {
  const input = document.querySelector<HTMLTextAreaElement>("#question");
  const button = document.querySelector<HTMLButtonElement>("#sendButton");
  if (!input || !button) return;

  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  button.disabled = true;
  addMessage("user", message);
  const assistantElement = addMessage("assistant", "");
  const paragraph = assistantElement.querySelector("p");
  if (!paragraph) return;

  renderCitations([]);

  try {
    const response = await fetch(`${currentBase()}/v1/chat/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        message,
        session_id: sessionId,
        workspace_id: "demo",
      }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const eventLine = frame
          .split("\n")
          .find((line) => line.startsWith("event:"));
        const dataLine = frame
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!eventLine || !dataLine) continue;

        const event = eventLine.slice(6).trim();
        const data = JSON.parse(dataLine.slice(5).trim());

        if (event === "token") {
          answer += String(data);
          paragraph.textContent = answer;
        }
        if (event === "tool_start") {
          paragraph.dataset.tool = String(data.name ?? "tool");
        }
        if (event === "done") {
          renderCitations((data.citations ?? []) as Citation[]);
        }
      }
    }
  } catch (error) {
    paragraph.textContent = `请求失败：${String(error)}`;
  } finally {
    button.disabled = false;
  }
}

document
  .querySelector<HTMLButtonElement>("#ingestButton")
  ?.addEventListener("click", () => void ingestText());

document
  .querySelector<HTMLButtonElement>("#sendButton")
  ?.addEventListener("click", () => void sendMessage());

document
  .querySelector<HTMLTextAreaElement>("#question")
  ?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      void sendMessage();
    }
  });

const dialog = document.querySelector<HTMLDialogElement>("#settingsDialog");
document
  .querySelector<HTMLButtonElement>("#settingsButton")
  ?.addEventListener("click", () => dialog?.showModal());

document
  .querySelector<HTMLButtonElement>("#saveSettings")
  ?.addEventListener("click", () => {
    const base =
      document.querySelector<HTMLInputElement>("#apiBaseInput")?.value.trim() ??
      defaultApiBase;
    const key =
      document.querySelector<HTMLInputElement>("#apiKeyInput")?.value.trim() ??
      "";
    localStorage.setItem("eduagentApiBase", base);
    localStorage.setItem("eduagentApiKey", key);
    window.location.reload();
  });

void checkHealth();
