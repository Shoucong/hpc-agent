"""LLM utility — wraps Ollama calls with structured output support."""

import json
import re
from langchain_ollama import ChatOllama
from hpc_agent.config import DEFAULT_MODEL


def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.0) -> ChatOllama:
    return ChatOllama(model=model, temperature=temperature)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def llm_json_call(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = None) -> dict:
    """Call LLM and parse JSON from response."""
    llm = get_llm(model)
    if max_tokens:
        llm = ChatOllama(model=model, temperature=0.0, num_predict=max_tokens)
    response = llm.invoke(prompt)
    text = _strip_thinking(response.content.strip())

    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM JSON", "raw": text}


def llm_text_call(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = None) -> str:
    """Call LLM and return plain text response."""
    llm = get_llm(model)
    if max_tokens:
        llm = ChatOllama(model=model, temperature=0.0, num_predict=max_tokens)
    response = llm.invoke(prompt)
    return _strip_thinking(response.content.strip())
