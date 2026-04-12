"""Centralized configuration for HPC Agent."""

# === Cluster Connection ===
# "mock" for testing without cluster, "ssh" for remote, "local" for running on login node
EXECUTOR_MODE = "ssh"

SSH_CONFIG = {
    "host": "172.16.1.133",
    "user": "cluster",
}

# === LLM ===
DEFAULT_MODEL = "batiai/gemma4-e4b:q4"
# === ReAct ===
MAX_REACT_ITERATIONS = 3
