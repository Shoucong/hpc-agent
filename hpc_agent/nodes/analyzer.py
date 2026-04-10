"""Analyzer node — ReAct-style: analyze, decide if more info is needed, or give final answer."""

from hpc_agent.state import AgentState
from hpc_agent.config import MAX_REACT_ITERATIONS
from hpc_agent.utils.llm import llm_json_call, llm_text_call

REACT_PROMPT = """你是 HPC 集群运维专家。用户问了一个问题，你已经收集了一些信息。

用户问题: {user_input}

已执行的命令和结果:
{command_history}

请判断：你现在掌握的信息是否足够回答用户的问题？

如果信息不够，你可以再执行一条 Slurm 命令来获取更多信息。
可用命令示例: sinfo, squeue, scontrol show job <id>, scontrol show node <name>, sacct, sstat -j <id>

返回 JSON（不要返回其他内容）:
如果信息足够:
{{"status": "done", "answer": "你的回答（简洁，不超过5句话）"}}

如果需要更多信息:
{{"status": "need_more", "thought": "我还需要知道...", "command": "要执行的命令"}}
"""


def _format_all_outputs(command_outputs: list[dict], react_history: list[dict]) -> str:
    """Format all collected outputs including react loop history."""
    parts = []

    for out in command_outputs:
        parts.append(f"$ {out['cmd']}")
        if out["exit_code"] != 0:
            parts.append(f"[ERROR exit={out['exit_code']}] {out['stderr']}")
        parts.append(out["stdout"].strip())
        parts.append("")

    for step in react_history:
        parts.append(f"[思考] {step.get('thought', '')}")
        parts.append(f"$ {step['command']}")
        parts.append(step["result"].strip())
        parts.append("")

    return "\n".join(parts)


def analyzer_node(state: AgentState) -> dict:
    """Analyze outputs. Either give final answer or request another command."""
    iteration = state.get("iteration_count", 0)
    react_history = state.get("react_history", [])

    # Safety: force final answer if we've looped too many times
    if iteration >= MAX_REACT_ITERATIONS:
        print(f"  [Analyzer] Max iterations ({MAX_REACT_ITERATIONS}) reached, forcing final answer")
        formatted = _format_all_outputs(state["command_outputs"], react_history)
        prompt = (
            f"你是 HPC 集群运维专家。根据以下信息回答用户问题，简洁回答不超过5句话。\n"
            f"用户问题: {state['user_input']}\n"
            f"收集到的信息:\n{formatted}"
        )
        answer = llm_text_call(prompt)
        return {
            "response": answer,
            "next_command": "",
            "follow_up_needed": False,
            "iteration_count": iteration,
        }

    # Build ReAct prompt
    formatted = _format_all_outputs(state["command_outputs"], react_history)
    prompt = REACT_PROMPT.format(
        user_input=state["user_input"],
        command_history=formatted,
    )

    result = llm_json_call(prompt)

    if result.get("status") == "need_more" and result.get("command"):
        thought = result.get("thought", "")
        command = result["command"]
        print(f"  [Analyzer] 思考: {thought}")
        print(f"  [Analyzer] 需要执行: {command}")
        return {
            "next_command": command,
            "follow_up_needed": True,
            "iteration_count": iteration + 1,
        }
    else:
        answer = result.get("answer", result.get("raw", "无法生成回答"))
        return {
            "response": answer,
            "next_command": "",
            "follow_up_needed": False,
            "iteration_count": iteration,
        }
