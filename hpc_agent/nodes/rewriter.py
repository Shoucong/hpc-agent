"""Query rewriter node — resolve references using conversation history."""

import re
from hpc_agent.state import AgentState
from hpc_agent.utils.llm import llm_text_call

# Patterns that suggest the user is referencing previous context
REFERENCE_PATTERNS = re.compile(
    r"(这个|那个|刚才|上面|它|上次|之前|同样|还是|怎么样了|什么情况了)",
    re.IGNORECASE,
)

REWRITE_PROMPT = """你是一个专注的query rewriter。你的唯一任务是把用户输入中的模糊指代词替换为具体内容，但绝不改变用户的原意、语气或删减任何字词。

【核心规则】
1. 仅将“这个”、“那个”、“它”等指代词，根据对话历史替换为具体的 Job ID 或节点名称。
2. 绝对保留用户原话中的所有附加要求、限定条件和口语（例如：“暂时不用管...”等必须保留）。
3. 严禁概括、严禁精简、严禁改写用户的句子结构。
4. 如果没有需要替换的指代词，直接原样返回完整输入。
5. 绝对禁止输出 <think> 标签或任何解释性文字。

【示例】
对话历史:
用户: 查一下 job 58
Agent: job 58 目前正在运行。
用户输入: 暂时不用管其他节点，现在呢，这个job完成了吗？运行多久了？
替换结果: 暂时不用管其他节点，现在呢，job 58完成了吗？运行多久了？

对话历史:
用户: 节点 cn02 负载很高
Agent: cn02 CPU使用率达到99%。
用户输入: 那它现在降下来了吗？其他节点也这样吗？
替换结果: 那 cn02 现在降下来了吗？其他节点也这样吗？

对话历史:
用户: 集群状态
Agent: 目前集群正常。
用户输入: 帮我提交一个新任务
替换结果: 帮我提交一个新任务

【当前任务】
对话历史:
{history}

用户最新输入: {user_input}
替换结果:"""


def rewriter_node(state: AgentState) -> dict:
    """Rewrite ambiguous user input using conversation history."""
    user_input = state["user_input"]
    history = state.get("conversation_history", [])

    # Skip if no history or no reference patterns detected
    if not history or not REFERENCE_PATTERNS.search(user_input):
        return {}  # no rewrite needed

    # Format recent history
    history_text = ""
    for msg in history[-6:]:
        role = "用户" if msg["role"] == "user" else "Agent"
        # Truncate long responses
        content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
        history_text += f"{role}: {content}\n"

    prompt = REWRITE_PROMPT.format(
        history=history_text,
        user_input=user_input,
    )

    rewritten = llm_text_call(prompt)

    if rewritten and rewritten != user_input:
        print(f"  [Rewriter] '{user_input}' → '{rewritten}'")
        return {"user_input": rewritten}
    else:
        print(f"  [Rewriter] No rewrite needed")
        return {}