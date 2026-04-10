"""React executor node — execute the command that Analyzer decided to run."""

from hpc_agent.state import AgentState
from hpc_agent.config import EXECUTOR_MODE, SSH_CONFIG
from hpc_agent.utils.command import CommandExecutor


def react_executor_node(state: AgentState) -> dict:
    """Execute the command from Analyzer's ReAct decision, append result to history."""
    cmd = state.get("next_command", "")
    if not cmd:
        return {}

    executor = CommandExecutor(mode=EXECUTOR_MODE, ssh_config=SSH_CONFIG)

    print(f"  [ReAct] Executing: {cmd}")
    result = executor.run(cmd)
    print(f"  [ReAct] exit={result.exit_code}, stdout={len(result.stdout)} chars")

    # Append to react history
    react_history = list(state.get("react_history", []))
    react_history.append({
        "thought": "",
        "command": cmd,
        "result": result.stdout if result.exit_code == 0 else f"ERROR: {result.stderr}",
    })

    return {
        "react_history": react_history,
        "next_command": "",
    }
