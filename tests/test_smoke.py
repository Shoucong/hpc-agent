"""Smoke test — run the full graph with mocked LLM calls (no Ollama needed)."""

import sys
import json
from unittest.mock import patch

# Mock LLM responses
def mock_json_call(prompt, model=None):
    """Fake router based on user input extracted from prompt."""
    if "102" in prompt:
        return {"skill": "job_diagnosis", "intent": "diagnose"}
    if "集群" in prompt or "状态" in prompt:
        return {"skill": "cluster_status", "intent": "monitor"}
    return {"skill": "cluster_status", "intent": "monitor"}


def mock_text_call(prompt, model=None):
    """Fake analyzer: return a canned analysis."""
    if "job" in prompt.lower() or "102" in prompt.lower():
        return (
            "Job 102 状态 PENDING，原因：Resources。\n"
            "请求 2 个节点，但当前只有 1 个空闲（cn02, cn03 idle，cn01 allocated，cn04 drain）。\n"
            "建议：减少节点请求到 1，或等待 job 101 完成。"
        )
    return (
        "集群共 4 个计算节点：\n"
        "- 3 个 idle（cn01-cn03）\n"
        "- 1 个 drain（cn04）\n"
        "队列中 1 个 running job（101），1 个 pending job（102，原因：Resources）。"
    )


@patch("hpc_agent.nodes.router.llm_json_call", mock_json_call)
@patch("hpc_agent.nodes.analyzer.llm_text_call", mock_text_call)
def run_test(user_input: str):
    from hpc_agent.agent import create_agent

    agent = create_agent()

    state = {
        "user_input": user_input,
        "conversation_history": [],
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
        "response": "",
        "iteration_count": 0,
    }

    result = agent.invoke(state)
    return result


def main():
    print("=" * 60)
    print("HPC Agent — Smoke Test (no Ollama needed)")
    print("=" * 60)

    # Test 1: cluster status
    print("\n--- Test 1: 集群状态查询 ---")
    print("Input: '集群什么情况？'")
    r = run_test("集群什么情况？")
    print(f"Skill:  {r['selected_skill']}")
    print(f"Intent: {r['intent']}")
    print(f"Commands run: {len(r['command_outputs'])}")
    for o in r["command_outputs"]:
        print(f"  - {o['name']}: {o['cmd']}")
    print(f"Response:\n{r['response']}")
    assert r["selected_skill"] == "cluster_status", f"Expected cluster_status, got {r['selected_skill']}"
    assert len(r["command_outputs"]) > 0, "Should have command outputs"
    assert r["response"], "Should have a response"
    print("✅ PASS")

    # Test 2: job diagnosis
    print("\n--- Test 2: Job 诊断 ---")
    print("Input: '为什么 job 102 一直 pending？'")
    r = run_test("为什么 job 102 一直 pending？")
    print(f"Skill:  {r['selected_skill']}")
    print(f"Intent: {r['intent']}")
    print(f"Job ID extracted: {r['cluster_context'].get('job_id')}")
    print(f"Commands run: {len(r['command_outputs'])}")
    for o in r["command_outputs"]:
        print(f"  - {o['name']}: {o['cmd']}")
    print(f"Response:\n{r['response']}")
    assert r["selected_skill"] == "job_diagnosis", f"Expected job_diagnosis, got {r['selected_skill']}"
    assert r["cluster_context"].get("job_id") == "102", "Should extract job_id 102"
    assert "102" in r["response"], "Response should mention the job"
    print("✅ PASS")

    print("\n" + "=" * 60)
    print("All tests passed! Graph pipeline works end-to-end.")
    print("=" * 60)


if __name__ == "__main__":
    main()
