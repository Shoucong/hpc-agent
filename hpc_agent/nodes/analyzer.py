"""Analyzer node — ReAct-style: analyze, decide if more info is needed, or give final answer."""

from hpc_agent.state import AgentState
from hpc_agent.config import MAX_REACT_ITERATIONS
from hpc_agent.utils.llm import llm_json_call, llm_text_call

# 优化后的 Prompt：加入了严格的 JSON 约束和 Few-Shot 示例
REACT_PROMPT = """你是高级 HPC 集群运维专家。请根据用户问题和已收集的信息，判断是否需要执行更多命令。

【核心规则】
1. 必须且只能输出一个合法的 JSON 对象，绝对禁止输出 <think> 标签或任何多余的解释文字。
2. 历史参考信息仅供了解背景；如果实时数据与历史有冲突，必须以实时数据为准。
3. 如果决定回答，请直接给出专业、有条理的诊断结论。
4. 如果某个命令的输出只有表头没有数据行（或标注了"无数据行"），说明结果为空，不要重复执行同一条命令。

【输出格式要求（二选一）】
如果信息足够回答问题，返回：
{{"status": "done", "answer": "你的最终分析结论"}}

如果需要更多信息才能排障，返回：
{{"status": "need_more", "thought": "你的推理过程（为什么需要更多信息）", "command": "具体要执行的 Slurm 命令"}}

【示例】
场景A (信息不足):
用户问题: 为什么 job 102 pending?
信息: 只有提交记录，没有具体排队原因。
输出: {{"status": "need_more", "thought": "目前不知道 job 102 的具体状态，需要查看详细信息才能判断 pending 原因。", "command": "scontrol show job 102"}}

场景B (信息足够):
用户问题: job 56 运行正常吗？
信息: squeue 显示 job 56 状态为 RUNNING，在 cn01 节点。
输出: {{"status": "done", "answer": "Job 56 目前处于正常运行状态（RUNNING），已成功分配到节点 cn01 上执行。"}}

【当前任务】
用户问题: {user_input}

已收集的信息与执行结果:
{command_history}

直接输出 JSON:
"""

def _format_all_outputs(command_outputs: list[dict], react_history: list[dict],
                        relevant_memory: list[dict] = None) -> str:
    """Format all collected outputs including react loop history and memory, with safety truncations."""
    parts = []

    # 1. 格式化初始命令输出（加入长度保护，防止大段日志撑爆上下文）
    for out in command_outputs:
        parts.append(f"$ {out['cmd']}")
        if out["exit_code"] != 0:
            parts.append(f"[ERROR exit={out['exit_code']}] {out.get('stderr', '')}")
        
        stdout = out.get('stdout', '').strip()
        # 截断超长输出，保留头部和尾部最关键的信息
        if len(stdout) > 2000:
            stdout = stdout[:1000] + "\n...[输出过长已截断]...\n" + stdout[-1000:]
        parts.append(stdout)
        parts.append("")

    # 2. 格式化 ReAct 迭代历史
    for step in react_history:
        parts.append(f"[思考] {step.get('thought', '')}")
        parts.append(f"$ {step['command']}")
        
        result = step.get('result', '').strip()
        if len(result) > 2000:
             result = result[:1000] + "\n...[输出过长已截断]...\n" + result[-1000:]
        parts.append(result)
        parts.append("")

    # 3. 格式化记忆上下文
    if relevant_memory:
        parts.append("=== 历史参考 ===")
        for mem in relevant_memory:
            if mem["source"] == "short_term":
                parts.append(f"[近期操作 {mem['timestamp']}] 问题: {mem['user_input']}")
                parts.append(f"  结论: {mem['analysis'][:200]}")
            elif mem["source"] == "long_term":
                parts.append(f"[知识库 相关度={mem.get('relevance', '?')}] {mem['knowledge']}")
            parts.append("")

    return "\n".join(parts)


def analyzer_node(state: AgentState) -> dict:
    """Analyze outputs. Either give final answer or request another command."""
    iteration = state.get("iteration_count", 0)
    react_history = state.get("react_history", [])

    formatted = _format_all_outputs(state.get("command_outputs", []), react_history,
                                    state.get("relevant_memory", []))

    # Safety: force final answer if we've looped too many times
    if iteration >= MAX_REACT_ITERATIONS:
        print(f"  [Analyzer] Max iterations ({MAX_REACT_ITERATIONS}) reached, forcing final answer")
        prompt = (
            f"你是 HPC 集群运维专家。根据以下信息直接回答用户问题，不要请求执行新命令。\n"
            f"用户问题: {state['user_input']}\n"
            f"收集到的信息:\n{formatted}\n"
            f"直接输出分析结论，绝对禁止包含 <think> 标签："
        )
        # 这里对于兜底逻辑使用 text_call 即可
        answer = llm_text_call(prompt, max_tokens=500) 
        return {
            "response": answer,
            "next_command": "",
            "follow_up_needed": False,
            "iteration_count": iteration,
        }

    # Build ReAct prompt
    prompt = REACT_PROMPT.format(
        user_input=state["user_input"],
        command_history=formatted,
    )

    result = llm_json_call(prompt)
    
    # 错误处理：如果小模型返回的不是有效的 JSON
    if "error" in result:
         print(f"  [Analyzer-Error] JSON 解析失败: {result['raw'][:100]}...")
         return {
            "response": "抱歉，分析节点在处理数据时出现格式错误，无法生成有效回答。",
            "next_command": "",
            "follow_up_needed": False,
            "iteration_count": iteration,
        }

    if result.get("status") == "need_more" and result.get("command"):
        thought = result.get("thought", "需要进一步探查")
        command = result["command"]
        print(f"  [Analyzer] 思考: {thought}")
        print(f"  [Analyzer] 需要执行: {command}")
        return {
            "next_command": command,
            "follow_up_needed": True,
            "iteration_count": iteration + 1,
        }
    else:
        # 提供默认的 fallback 文本
        answer = result.get("answer", "根据目前信息，未发现明显异常或信息不足以作出判断。")
        return {
            "response": answer,
            "next_command": "",
            "follow_up_needed": False,
            "iteration_count": iteration,
        }