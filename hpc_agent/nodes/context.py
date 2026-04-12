"""Context node — collect cluster state and relevant memory for the selected skill."""

import re
from hpc_agent.state import AgentState
from hpc_agent.config import EXECUTOR_MODE, SSH_CONFIG
from hpc_agent.skills.loader import load_skills
from hpc_agent.utils.command import CommandExecutor
from hpc_agent.memory.short_term import ShortTermMemory
from hpc_agent.memory.long_term import LongTermMemory

def _extract_job_id(user_input: str) -> str | None:
    """Try to extract a job ID from user input."""
    match = re.search(r"(?:job\s*(?:id\s*)?|任务|作业)\s*(\d+)", user_input, re.IGNORECASE)
    return match.group(1) if match else None


def context_node(state: AgentState) -> dict:
    """Run the skill's context commands and collect outputs."""
    skills = load_skills()
    skill_name = state["selected_skill"]

    if skill_name not in skills:
        return {
            "cluster_context": {},
            "commands_to_run": [],
            "command_outputs": [],
        }

    skill = skills[skill_name]
    executor = CommandExecutor(mode=EXECUTOR_MODE, ssh_config=SSH_CONFIG)

    # Extract parameters from user input
    job_id = _extract_job_id(state["user_input"])

    outputs = []
    for cmd_def in skill.get("context_commands", []):
        cmd = cmd_def["cmd"]

        # Fill placeholders
        if "{job_id}" in cmd:
            if not job_id:
                print(f"  [Context] Skipped {cmd_def['name']}: no job_id found")
                continue
            cmd = cmd.replace("{job_id}", job_id)

        result = executor.run(cmd)
        print(f"  [Context] {cmd_def['name']}: exit={result.exit_code}, stdout={len(result.stdout)} chars")
        if result.stderr:
            print(f"  [Context]   stderr: {result.stderr[:200]}")

        stdout = result.stdout
        # Mark empty squeue/sacct results clearly
        if result.exit_code == 0 and len(stdout.strip().split('\n')) <= 1:
            if any(cmd_word in cmd for cmd_word in ['squeue', 'sacct']):
                stdout = stdout.strip() + "\n(无数据行 — 当前没有匹配的任务)"

        outputs.append(
            {
                "name": cmd_def["name"],
                "cmd": cmd,
                "stdout": stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
            }
        )

    # Retrieve relevant memory
    memory_items = []

    # Short-term: recent similar operations
    try:
        stm = ShortTermMemory()
        recent = stm.get_recent(skill=skill_name, limit=3)
        for r in recent:
            memory_items.append({
                "source": "short_term",
                "timestamp": r["timestamp"],
                "user_input": r["user_input"],
                "analysis": r["analysis"],
            })
        if recent:
            print(f"  [Context] Found {len(recent)} short-term memories")
    except Exception as e:
        print(f"  [Context] Short-term memory error: {e}")

    # Long-term: semantically similar knowledge
    try:
        ltm = LongTermMemory()
        if ltm.count() > 0:
            similar = ltm.search(query=state["user_input"], n_results=3, skill=skill_name)
            for s in similar:
                memory_items.append({
                    "source": "long_term",
                    "knowledge": s["text"],
                    "relevance": round(1 - (s["distance"] or 0), 2),
                })
            if similar:
                print(f"  [Context] Found {len(similar)} long-term memories")
    except Exception as e:
        print(f"  [Context] Long-term memory error: {e}")

    return {
        "command_outputs": outputs,
        "cluster_context": {"job_id": job_id},
        "relevant_memory": memory_items,
    }