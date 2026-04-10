"""HPC Agent state definition."""

from typing import TypedDict, Optional


class AgentState(TypedDict):
    # Input
    user_input: str
    conversation_history: list[dict]

    # Router output
    selected_skill: str
    intent: str  # diagnose | monitor | operate | optimize

    # Context
    cluster_context: dict
    relevant_memory: list[dict]

    # Execution
    commands_to_run: list[str]
    command_outputs: list[dict]  # {cmd, stdout, stderr, exit_code}

    # Analysis
    analysis: str
    confidence: float
    follow_up_needed: bool
    follow_up_question: str

    # ReAct loop
    next_command: str           # LLM decides what to run next (empty = done)
    react_history: list[dict]   # [{thought, command, result}, ...]

    # Final
    response: str

    # Control
    iteration_count: int
