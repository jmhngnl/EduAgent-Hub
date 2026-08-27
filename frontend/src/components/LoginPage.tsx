import { useState } from "react";
import { login, register } from "../auth/api";
import { useAuthStore } from "../auth/useAuthStore";

export function LoginPage() {
  const setSession = useAuthStore((state) => state.setSession);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      const session = mode === "login"
        ? await login(username.trim(), password)
        : await register(username.trim(), password, displayName.trim());
      setSession(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Authentication failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand"><span>E</span><div><strong>EduAgent Hub</strong><small>Enterprise Agent Platform · V2.2</small></div></div>
        <div className="auth-tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>登录</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>注册</button>
        </div>
        {mode === "register" && (
          <label>显示名称<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Researcher" /></label>
        )}
        <label>用户名<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" /></label>
        <label>密码<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 8 位" onKeyDown={(e) => { if (e.key === "Enter") void submit(); }} /></label>
        {error && <div className="auth-error">{error}</div>}
        <button className="auth-submit" disabled={pending || !username.trim() || password.length < 8 || (mode === "register" && !displayName.trim())} onClick={() => void submit()}>
          {pending ? "处理中..." : mode === "login" ? "登录 EduAgent" : "创建账号"}
        </button>
        <p className="auth-note">第一个注册/Bootstrap 用户会成为 <code>demo</code> Workspace 的 OWNER，并自动认领 V2.1 历史对话。</p>
      </section>
    </main>
  );
}
