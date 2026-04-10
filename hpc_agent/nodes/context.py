"""Context node — collect cluster state and relevant memory for the selected skill."""

import re
from hpc_agent.state import AgentState
from hpc_agent.config import EXECUTOR_MODE, SSH_CONFIG
from hpc_agent.skills.loader import load_skills
from hpc_agent.utils.command import CommandExecutor


def _extract_job_id(user_input: str) -> str | None:
    """Try to extract a job ID from user input."""
    match = re.search(r"(?:job|任务|作业)\s*(\d+)", user_input, re.IGNORECASE)
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

        outputs.append(
            {
                "name": cmd_def["name"],
                "cmd": cmd,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
            }
        )

    return {
        "command_outputs": outputs,
        "cluster_context": {"job_id": job_id},
        "relevant_memory": [],  # TODO: hook up memory retrieval
    }
