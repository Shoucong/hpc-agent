import threading
from hpc_agent.state import AgentState
from hpc_agent.memory.short_term import ShortTermMemory
from hpc_agent.memory.long_term import LongTermMemory
from hpc_agent.utils.llm import llm_json_call

# 采用 JSON 格式和严格的 Few-Shot 示例，强制模型进行价值判断
KNOWLEDGE_EXTRACT_PROMPT = """你是一个 HPC 集群运维专家系统的“经验萃取器”。
你的任务是判断刚才的运维操作是否产生了【通用、有价值的排障/诊断经验】，并提取出来。

【严格定义：什么是有价值的经验？】
- 发现了具体的节点故障（如 DOWN、NOT_RESPONDING）及其原因。
- 发现了导致 Job Pending 或 Failed 的具体原因（如资源不足、配置错误）。
- 采取了具体的排查命令或修复动作。

【严格定义：什么是无价值的经验？（必须判定为 false）】
- 正常的 Job 状态查询（如：job 正在正常运行、job 已完成）。
- 正常的节点状态查询。
- 没有任何异常的常规统计信息。

请以 JSON 格式输出，包含以下两个字段：
"is_valuable": 布尔值（true 或 false）。
"knowledge": 字符串。如果 is_valuable 为 true，使用格式“当[具体症状]时，原因通常是[具体原因]，排查/解决方法是[具体步骤]”。如果为 false，留空字符串。

【示例 1】
用户问题: 为什么 job 102 pending?
分析结论: 任务请求了2个节点，但目前集群资源不足，处于 resources 状态。
输出: {{"is_valuable": true, "knowledge": "当 job 处于 PENDING 且原因为 Resources 时，通常是因为请求的节点数大于当前空闲节点数，需使用 sinfo 检查资源或减少 --nodes 请求。"}}

【示例 2】
用户问题: job 56现在怎么样了？
分析结论: Job 56 目前处于正常运行状态（RUNNING），已运行18秒。
输出: {{"is_valuable": false, "knowledge": ""}}

【当前任务】
用户问题: {user_input}
使用的 Skill: {skill}
分析结论: {analysis}

直接返回 JSON：
"""

def _extract_and_save_ltm(user_input: str, skill: str, response: str, intent: str):
    import time, json, re
    start = time.time()

    prompt = KNOWLEDGE_EXTRACT_PROMPT.format(
        user_input=user_input,
        skill=skill,
        analysis=response,
    )

    from hpc_agent.utils.llm import get_llm
    llm = get_llm()
    raw = llm.invoke(prompt).content

    # Extract JSON from anywhere in the response
    json_match = re.search(r'\{[^{}]*"is_valuable"[^{}]*\}', raw, re.DOTALL)
    if not json_match:
        print(f"\n  [Memory] (后台) 未找到 JSON")
        return

    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        print(f"\n  [Memory] (后台) JSON解析失败: {json_match.group()[:100]}")
        return

    if result.get("is_valuable") is True:
        knowledge = result.get("knowledge", "")
        if knowledge and len(knowledge) > 10:
            ltm = LongTermMemory()
            ltm.save(
                text=knowledge,
                metadata={"skill": skill, "intent": intent},
            )
            print(f"\n  [Memory] (后台) 成功提取长期经验: {knowledge[:50]}...")
    else:
        print(f"\n  [Memory] (后台) 判定为无价值经验，跳过存储")

    elapsed = time.time() - start
    print(f"  [Memory] (后台) Long-term completed in {elapsed:.1f}s")

def memory_node(state: AgentState) -> dict:
    """Save this interaction to short-term and long-term memory."""
    skill = state.get("selected_skill", "none")
    response = state.get("response", "")

    if skill == "none" or not response:
        return {}

    # Don't save memory for failed connections
    commands = state.get("command_outputs", [])
    all_failed = all(c.get("exit_code", 0) != 0 for c in commands) if commands else True
    if all_failed:
        print(f"  [Memory] Skipped — all commands failed")
        return {}

    # 1. Short-term: save raw operation record (主线程中快速执行)
    stm = ShortTermMemory()
    react_history = state.get("react_history", [])
    cmd_summary = [{"cmd": c["cmd"], "exit": c["exit_code"]} for c in commands]
    cmd_summary += [{"cmd": r["command"], "source": "react"} for r in react_history]

    stm.save(
        user_input=state["user_input"],
        skill=skill,
        intent=state.get("intent", ""),
        commands=cmd_summary,
        analysis=response,
        react_steps=len(react_history),
    )
    print(f"  [Memory] Saved to short-term memory")
    stm.cleanup(days=7)

    # 2. Long-term: 使用后台线程异步处理，不阻塞用户的等待时间
    print(f"  [Memory] Long-term memory extraction started in background...")
    thread = threading.Thread(
        target=_extract_and_save_ltm,
        args=(state["user_input"], skill, response, state.get("intent", ""))
    )
    thread.daemon = True # 设置为守护线程，主程序退出时它也会退出
    thread.start()

    return {}