# On-Call Assistant

基于 LLM 与 Tool Runtime 的智能 On-Call 助手系统，通过受控工具调用（Tool Calling）、文档检索（Retrieval）以及可观测执行流程（Trace），实现对运维场景问题的自动分析与回答。

项目并非仅关注模型输出能力，而是更强调 Agent 系统在工程环境中的稳定性、可控性与可观测性。开发过程中采用渐进式架构设计，从 Deterministic Runtime 开始，逐步扩展到 Tool Runtime、Retrieval Pipeline 以及 Agent 层能力。

---

## 功能特性

- V1：精确检索
- V2：语义检索（BM25 + Synonym Expansion + Embedding（可选，默认关闭 = False））
- V3：Tool 驱动 Agent workFlow
- 前端聊天界面与模式切换
- 支持历史搜索记录的回退和删除
- Tool 调用过程 Trace 侧边栏展示，可查看单步详细参数返回
- Recovery 与 Rollback 机制

当前已实现部分 Defensive Programming 能力：

- 拒绝空文件名
- 拒绝通配符访问
- 拒绝路径穿越
- Tool Schema 校验
- Timeout 保护
- 独立 Recovery 流程

---

## 系统架构

```text
User
   │
Frontend UI
   │
Answer Composer
   │
Agent Runtime
   │
   ├── Retrieval Pipeline
   │
   ├── Tool Runtime
   │          │
   │          └── readFile()
   │
   └── LLM Adapter
```

---

## 项目结构

```text
project/

├── app/
│   ├── agent/
│   ├── retrieval/
│   ├── tool_runtime/
│   ├── adapter/
│   └── api/

├── frontend/
├── tests/
├── data/
├── docs/
└── README.md
```

---

## 快速启动

安装依赖：

```bash
pip install -r requirements.txt

cd frontend
npm install
```

配置环境变量：

```bash
cp .env.example .env
```

填写：

```text
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=xxx
MODEL=xxx
```

启动后端：

```bash
uvicorn app.main:app --reload
```

启动前端：

```bash
cd frontend

npm run dev
```

默认访问：

```text
Backend:
http://localhost:8000

API Docs:
http://localhost:8000/docs

Frontend:
http://localhost:5173
```

---

## 测试

运行全部测试：

```bash
pytest
```

运行指定模块：

```bash
pytest tests/test_tool_runtime.py
pytest tests/test_manifest_builder.py
```

---

## 开发思路

```text
项目开发顺序:
1. Deterministic Runtime
2. Tool System
3. Retrieval
4. Single Agent
5. Multi-Agent
```
- 优先保证 Runtime 稳定性
- 优先保证系统分区 功能独立 和 状态隔离
- 优先保证 rollback 能力
- 优先保证 实现过程可追踪性

---

## 后续规划

- Multi-Agent 架构
- Memory 系统
- Evaluator
- RAG 优化
- Observability Dashboard