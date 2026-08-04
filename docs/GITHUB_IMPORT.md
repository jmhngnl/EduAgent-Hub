# 导入到 `jmhngnl/lab-ly`

当前目标仓库是 DevDojo Static/Tailwind 的实验室静态官网，本项目应作为独立子目录加入，避免破坏原有 GitHub Pages 构建。

推荐目录：

```text
lab-ly/
├── 原有静态官网文件
└── ai-agent-platform/
    └── 本项目全部文件
```

## 方法一：直接复制

```bash
git clone https://github.com/jmhngnl/lab-ly.git
cd lab-ly
mkdir ai-agent-platform
cp -R /path/to/eduagent-hub/. ai-agent-platform/
git checkout -b feat/resume-grade-ai-agent-platform
git add ai-agent-platform
git commit -m "feat(ai): add EduAgent Hub agent and RAG platform"
git push -u origin feat/resume-grade-ai-agent-platform
```

## 方法二：应用补丁

本次交付同时提供 `.patch` 文件：

```bash
cd lab-ly
git am /path/to/lab-ly-eduagent-hub.patch
```

导入后建议为根 README 增加一个 “AI Agent Platform” 小节，并链接到 `ai-agent-platform/README.md`。


## GitHub Actions

如果以子目录方式导入，工作流必须放在仓库根目录：

```text
.github/workflows/ai-agent-platform.yml
```

本次提供的 `.patch` 已自动将工作流转换并放到正确位置。ZIP 中的工作流面向
“该项目单独作为一个仓库”的场景；手动复制为 `lab-ly/ai-agent-platform/` 子目录时，
请将工作流移动到根目录，并把 `working-directory` 和 `paths` 增加
`ai-agent-platform/` 前缀。
