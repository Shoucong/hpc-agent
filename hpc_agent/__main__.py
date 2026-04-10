"""CLI entry point — interactive chat loop."""

import readline  # noqa: F401 — fixes Chinese input deletion in macOS terminal
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from hpc_agent.agent import create_agent

console = Console()


def main():
    console.print(
        Panel(
            "[bold green]HPC Cluster Operations Agent[/bold green]\n"
            "输入集群相关问题，输入 quit 退出。\n"
            "示例: 集群什么状态？ / 为什么 job 102 pending？",
            title="🖥️  HPC Agent",
            border_style="green",
        )
    )

    agent = create_agent()

    history = []

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]再见！[/dim]")
            break

        # Build initial state
        state = {
            "user_input": user_input,
            "conversation_history": history[-6:],  # keep last 3 turns
            "selected_skill": "none",
            "intent": "",
            "cluster_context": {},
            "relevant_memory": [],
            "commands_to_run": [],
            "command_outputs": [],
            "analysis": "",
            "confidence": 0.0,
            "follow_up_needed": False,
            "follow_up_question": "",
            "next_command": "",
            "react_history": [],
            "response": "",
            "iteration_count": 0,
        }

        # Run agent
        console.print("[dim]思考中...[/dim]")
        result = agent.invoke(state)

        response = result.get("response", "")
        skill = result.get("selected_skill", "none")

        if response:
            console.print()
            console.print(
                Panel(
                    Markdown(response),
                    title=f"Agent [dim]({skill})[/dim]",
                    border_style="blue",
                )
            )
        else:
            console.print("[yellow]Agent 没有生成回复。[/yellow]")

        # Update history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
