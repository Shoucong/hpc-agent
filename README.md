# HPC Cluster Operations Agent

基于 LangGraph 的本地 HPC 集群智能运维 Agent。通过自然语言与 Slurm 集群交互，具备自主推理能力（ReAct loop），能够根据观察结果动态决定下一步操作。

## 核心特性

- **ReAct 自主推理循环** — Agent 分析初始信息后，自主决定是否需要更多数据，动态选择并执行 Slurm 命令（最多 3 轮）
- **混合路由** — 关键词快速匹配（0s） + LLM 兜底（~13s），常见请求零延迟路由
- **YAML Skill 系统** — 可扩展的 plugin 架构，新增运维场景只需写配置
- **本地 LLM** — Ollama 驱动，无需云端 API，数据不离开本地

## 架构

```
用户输入
    │
    ▼
  Router ──── 关键词匹配(0s) / LLM分类(fallback)
    │
    ▼
  Context ─── 执行 Skill YAML 中定义的固定命令
    │
    ▼
  Analyzer ── LLM 分析输出 → 信息够了？
    │                           │
    │ 不够                      │ 够了
    ▼                           ▼
  ReAct Executor               Memory → 输出
  (LLM 自主选择命令)              │
    │                           │
    └── 回到 Analyzer ──────────┘
```

**设计思想：** LLM 只负责两件事——路由（选 Skill）和分析（读输出写结论）。命令定义、执行、解析全部是确定性代码，使本地 7-9B 模型完全够用。ReAct 循环在此基础上增加了自主决策能力：Agent 可以根据初始信息不足主动获取更多数据。

## 快速开始

```bash
# 克隆项目
git clone https://github.com/<your-username>/hpc-agent.git
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

```
> 集群什么状态？
  [Router] Keyword match → cluster_status (0.0s)
  [Context] sinfo, squeue (0.8s)
  [Analyzer] 发现 cn04 down，自主执行 scontrol show node cn04
  [ReAct] 获取节点详情 (0.4s)
  [Analyzer] 综合分析 (24s)

Agent: 集群 4 个节点中 cn01 idle 可用，cn02-04 处于 DOWN+NOT_RESPONDING 状态...

> 为什么 job 52 pending?
  [Router] Keyword match → job_diagnosis (0.0s)
  [Analyzer] 自主执行 squeue -j 52 → 发现实际是 RUNNING
  [Analyzer] 自主执行 scontrol show job 52 → 获取详情

Agent: Job 52 目前不是 Pending 而是 RUNNING，已在 cn01 上运行...

> cn04 为什么 drain 了，能恢复吗？
  [Analyzer] 自主执行 scontrol show node cn04
  
Agent: cn04 状态是 DOWN+NOT_RESPONDING，非手动 drain。
       Slurm 检测到节点长时间无响应，触发超时机制。
       建议检查网络连接和硬件状态...
```

## 项目结构

```
hpc_agent/
├── config.py              # 集中配置（连接模式、模型、参数）
├── agent.py               # LangGraph 主流程（含 ReAct 循环）
├── state.py               # AgentState 定义
├── __main__.py            # CLI 入口
├── nodes/
│   ├── router.py          # 关键词匹配 + LLM 兜底路由
│   ├── context.py         # 执行 Skill 定义的命令
│   ├── analyzer.py        # ReAct 分析（自主决定是否需要更多信息）
│   ├── react_executor.py  # 执行 Analyzer 动态请求的命令
│   └── memory.py          # 记忆存储（Phase 2）
├── skills/
│   ├── loader.py          # YAML Skill 加载器
│   └── definitions/
│       ├── cluster_status.yaml
│       └── job_diagnosis.yaml
├── parsers/               # 命令输出解析器（Phase 2）
├── memory/                # 记忆系统（Phase 2）
└── utils/
    ├── llm.py             # Ollama 调用封装（自动去除 thinking 块）
    └── command.py         # 命令执行器（mock / local / SSH）
```

## 配置

所有配置集中在 `config.py`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `EXECUTOR_MODE` | 命令执行模式：`mock` / `local` / `ssh` | `"ssh"` |
| `SSH_CONFIG` | SSH 连接信息 | `{"host": "172.16.1.133", "user": "cluster"}` |
| `DEFAULT_MODEL` | Ollama 模型名称 | `"qwen3.5:9b"` |
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
- [ ] **Phase 2** — 三层记忆系统（Working / Short-term SQLite / Long-term ChromaDB）
- [ ] **Phase 3** — 更多 Skills（node_diagnosis, job_submit, log_analysis），安全确认机制
- [ ] **Phase 4** — TUI 美化，Demo 录屏，完善文档

## 技术栈

| 组件 | 选型 |
|------|------|
| Agent 框架 | LangGraph |
| LLM | Ollama + local models |
| Skill 定义 | YAML |
| 集群调度 | Slurm |
| 向量存储（planned） | ChromaDB |
| CLI 美化 | Rich |

## License

MIT
