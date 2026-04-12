# HPC Cluster Operations Agent

基于 LangGraph 的本地 HPC 集群智能运维 Agent。通过自然语言与 Slurm 集群交互，具备 ReAct 自主推理、三层记忆系统和上下文关联能力，完全本地运行。

## 核心特性

- **ReAct 自主推理循环** — Agent 分析初始信息后，自主决定是否需要更多数据，动态选择并执行 Slurm 命令
- **三层记忆系统** — Working Memory（当前对话）+ Short-term（SQLite，7 天操作日志）+ Long-term（ChromaDB，语义检索诊断经验），支持跨会话知识积累
- **Query Rewriter** — 自动解析模糊指代，结合对话历史重写为完整查询
- **混合路由** — 关键词快速匹配（0s）+ LLM 兜底（~5s），常见请求零延迟路由
- **YAML Skill 系统** — 可扩展的 plugin 架构，新增运维场景只需写配置文件
- **本地 LLM** — Ollama 驱动，无需云端 API，数据不离开本地

## 架构

```
用户输入
    │
    ▼
  Rewriter ── 检测到"这个/那个/刚才"? → LLM 重写为完整查询
    │                                  → 否则跳过 (0s)
    ▼
  Router ──── 关键词匹配(0s) / LLM分类(fallback)
    │
    ▼
  Context ─── 执行 Skill YAML 中定义的命令
    │          + 检索 Short-term & Long-term 记忆
    ▼
  Analyzer ── LLM 分析(命令输出 + 历史记忆) → 信息够了？
    │                                          │
    │ 不够                                     │ 够了
    ▼                                          ▼
  ReAct Executor                              Memory → 输出
  (LLM 自主选择命令)                             │
    │                                          │
    └──────── 回到 Analyzer ───────────────────┘

Memory 节点:
  ├── Short-term (SQLite) ← 同步写入，记录操作日志
  └── Long-term (ChromaDB) ← 异步后台线程，LLM 判断价值后存储
```

**设计思想：** LLM 只负责决策（路由、分析、价值判断），命令定义和执行全部是确定性代码，使本地 7-9B 模型完全够用。固定命令打底 + ReAct 自主扩展的混合设计兼顾了可靠性和灵活性。

## 快速开始

```bash
# 克隆项目
git clone https://github.com/Shoucong/hpc-agent.git
cd hpc-agent

# 创建环境
conda create -n hpc-agent python=3.11 -y
conda activate hpc-agent
pip install -r requirements.txt

# 拉取模型
ollama pull gemma4:e4b

# 配置连接（编辑 config.py）
# EXECUTOR_MODE = "ssh" / "mock" / "local"
# SSH_CONFIG = {"host": "your-login-node-ip", "user": "your-user"}

# Mock 模式测试（无需集群）
# 将 config.py 中 EXECUTOR_MODE 改为 "mock"
python -m tests.test_smoke

# 运行
python -m hpc_agent
```

## 使用示例

### 集群状态查询
```
> 集群什么状态？
  [Router] Keyword match → cluster_status (0.0s)
  [Context] sinfo, squeue (0.8s)
  [Analyzer] 发现 cn02-04 down，自主执行 scontrol show node cn02 (ReAct)
  
Agent: 集群 4 节点中 cn01 idle 可用，cn02-04 处于 DOWN+NOT_RESPONDING 状态。
       建议检查这些节点的网络连接和硬件状态。
```

### Job 诊断 + ReAct 自主纠错
```
> 为什么 job 52 pending?
  [Analyzer] 自主执行 squeue -j 52 → 发现实际是 RUNNING
  [Analyzer] 自主执行 scontrol show job 52 → 获取详情

Agent: Job 52 目前不是 Pending 而是 RUNNING，已在 cn01 上运行...
```

### 上下文关联（Query Rewriter）
```
> job 60 现在什么情况？
Agent: Job 60 正在 cn01 上运行，已运行 54 秒...

> 暂时不用管其他节点，这个任务运行多久了？
  [Rewriter] → '暂时不用管其他节点，Job ID 60 现在运行多久了？'

Agent: 根据实时数据，Job 60 已运行 2 分 55 秒 (00:02:55)...
```

### 记忆系统生效（跨会话）
```
# 第一次会话
> cn04 为什么 drain 了？
Agent: DOWN+NOT_RESPONDING，建议检查网络和重启 slurmd
  [Memory] 成功提取长期经验: 当节点状态为 DOWN+NOT_RESPONDING 时...

# 重启 agent 后的新会话
> 集群什么状态？
  [Context] Found 3 short-term memories
  [Context] Found 1 long-term memories    ← 检索到上次的诊断经验

Agent: ...cn02-04 处于 down 状态（参考历史记录，上次也出现过类似的 NOT_RESPONDING 问题）
```

## 项目结构

```
hpc_agent/
├── config.py              # 集中配置（连接模式、模型、参数）
├── agent.py               # LangGraph 主流程（含 ReAct 循环）
├── state.py               # AgentState 定义
├── __main__.py            # CLI 入口
├── nodes/
│   ├── rewriter.py        # Query Rewriter（指代消解）
│   ├── router.py          # 关键词匹配 + LLM 兜底路由
│   ├── context.py         # 执行命令 + 检索记忆
│   ├── analyzer.py        # ReAct 分析（Few-shot + JSON 约束）
│   ├── react_executor.py  # 执行 Analyzer 动态请求的命令
│   └── memory.py          # 记忆存储（异步 Long-term + 同步 Short-term）
├── skills/
│   ├── loader.py          # YAML Skill 加载器
│   └── definitions/
│       ├── cluster_status.yaml
│       └── job_diagnosis.yaml
├── memory/
│   ├── short_term.py      # SQLite 操作日志（7 天滚动）
│   └── long_term.py       # ChromaDB 语义知识库（持久）
└── utils/
    ├── llm.py             # Ollama 封装（thinking 去除、max_tokens）
    └── command.py         # 命令执行器（mock / local / SSH）
```

## 配置

所有配置集中在 `config.py`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `EXECUTOR_MODE` | 命令执行模式：`mock` / `local` / `ssh` | `"ssh"` |
| `SSH_CONFIG` | SSH 连接信息 | `{"host": "172.16.1.133", "user": "cluster"}` |
| `DEFAULT_MODEL` | Ollama 模型名称 | `"gemma4:e4b"` |
| `MAX_REACT_ITERATIONS` | ReAct 最大循环次数 | `3` |

## 测试环境

在自建的 6 节点 Slurm 集群上验证（VMware Fusion Pro, Ubuntu Server 24.04 ARM64）：

```
Mac (host) ─── VMware Fusion Pro
  ├── login  (172.16.1.133) — SSH 入口，提交 job
  ├── mgmt   (172.16.1.134) — slurmctld + slurmdbd + MariaDB + NFS
  ├── cn01   (192.168.64.21) — 计算节点，1 CPU, 900MB
  ├── cn02   (192.168.64.22) — 计算节点
  ├── cn03   (192.168.64.23) — 计算节点
  └── cn04   (192.168.64.24) — 计算节点
```

## 开发路线

- [x] **Phase 0** — 项目骨架，LangGraph graph 跑通，mock 测试
- [x] **Phase 1** — SSH 真实集群集成，ReAct 自主推理循环，关键词快速路由
- [x] **Phase 2** — 三层记忆系统，Query Rewriter，Analyzer 优化（Few-shot / JSON 约束 / 输出截断 / 错误兜底）
- [ ] **Phase 3** — 更多 Skills（node_diagnosis, job_submit, log_analysis），安全确认机制，Slurm Parser
- [ ] **Phase 4** — TUI 美化，Demo 录屏，完善文档与测试

## 技术栈

| 组件 | 选型 |
|------|------|
| Agent 框架 | LangGraph |
| LLM | Ollama + Gemma 4 E4B |
| Skill 定义 | YAML |
| 集群调度 | Slurm |
| 短期记忆 | SQLite |
| 长期记忆 | ChromaDB |
| CLI 美化 | Rich |

## 技术亮点

| 设计决策 | 解决的问题 |
|----------|-----------|
| LLM 只做决策，代码做执行 | 本地 7-9B 模型能力有限，通过架构设计规避短板 |
| 固定命令打底 + ReAct 自主扩展 | 兼顾可靠性（YAML 定义的命令一定执行）和灵活性（LLM 可以追加命令） |
| 关键词匹配 + LLM 兜底路由 | 常见请求 0s 路由，罕见请求仍有 LLM 覆盖 |
| 三层记忆分工 | Working Memory 管当前对话，Short-term 管操作日志，Long-term 管诊断经验 |
| Long-term 异步写入 + 价值判断 | 不阻塞用户，且只存有诊断价值的知识 |
| 输出截断 + 空结果标注 | 防止大段输出撑爆 context，防止 Analyzer 重复执行空查询 |
| Few-shot + JSON 结构化约束 | 提高本地小模型的输出可靠性 |

## License

MIT