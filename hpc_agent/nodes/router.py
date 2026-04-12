"""Router node — keyword fast-match first, LLM fallback."""

import re
from hpc_agent.state import AgentState
from hpc_agent.utils.llm import llm_json_call
from hpc_agent.skills.loader import load_skills, get_skill_summary

# Keyword rules: (pattern, skill, intent)
KEYWORD_RULES = [
    (r"(集群|cluster|sinfo).*(状态|状况|情况|status|怎么样)", "cluster_status", "monitor"),
    (r"(节点|node).*(状态|情况|status)", "cluster_status", "monitor"),
    (r"(job|任务|作业).*(pending|失败|fail|timeout|stuck|排队|为什么|怎么)", "job_diagnosis", "diagnose"),
    (r"(为什么|why).*(job|任务|作业)", "job_diagnosis", "diagnose"),
    (r"(drain|down|故障|恢复)", "cluster_status", "diagnose"),
    (r"(job|任务|作业|Job ID)\s*\d+", "job_diagnosis", "diagnose"),
]

ROUTER_PROMPT = """你是一个 HPC 集群运维助手的路由器。
根据用户输入，选择最合适的 skill，并判断用户意图类别。

可用 skills:
{skill_list}

用户输入: {user_input}

返回 JSON（不要返回其他内容）:
{{"skill": "skill名称", "intent": "diagnose|monitor|operate|optimize"}}

如果不属于任何 skill，返回:
{{"skill": "none", "intent": "chat"}}
"""


def _keyword_match(user_input: str) -> tuple[str, str] | None:
    """Try to match user input against keyword rules."""
    text = user_input.lower()
    for pattern, skill, intent in KEYWORD_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return skill, intent
    return None


def router_node(state: AgentState) -> dict:
    """Route: keyword match first (0s), LLM fallback (~13s)."""
    user_input = state["user_input"]

    # Fast path: keyword matching
    match = _keyword_match(user_input)
    if match:
        skill, intent = match
        print(f"  [Router] Keyword match → {skill}")
        return {"selected_skill": skill, "intent": intent}

    # Slow path: LLM fallback
    print("  [Router] No keyword match, using LLM...")
    skills = load_skills()
    skill_list = get_skill_summary(skills)
    prompt = ROUTER_PROMPT.format(skill_list=skill_list, user_input=user_input)
    result = llm_json_call(prompt)

    if "error" in result:
        print(f"  [Router-Error] JSON parse failed, fallback to none")
        return {"selected_skill": "none", "intent": "chat"}

    return {
        "selected_skill": result.get("skill", "none"),
        "intent": result.get("intent", "chat"),
    }
