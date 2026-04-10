"""Command execution utility.

Supports two modes:
  - local: subprocess (for when agent runs ON the cluster login node)
  - ssh:   paramiko SSH (for when agent runs on Mac, connecting to cluster)

For now we implement local mode + a mock mode for testing.
"""

import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    cmd: str
    stdout: str
    stderr: str
    exit_code: int

    def to_dict(self) -> dict:
        return {
            "cmd": self.cmd,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
        }


class CommandExecutor:
    """Execute shell commands. Subclass or swap for SSH/mock as needed."""

    def __init__(self, mode: str = "local", ssh_config: dict | None = None):
        self.mode = mode
        self.ssh_config = ssh_config

    def run(self, cmd: str, timeout: int = 30) -> CommandResult:
        if self.mode == "mock":
            return self._run_mock(cmd)
        if self.mode == "ssh":
            return self._run_ssh(cmd, timeout)
        return self._run_local(cmd, timeout)

    def _run_ssh(self, cmd: str, timeout: int) -> CommandResult:
        """Execute command on remote host via SSH."""
        host = self.ssh_config.get("host", "172.16.1.133")
        user = self.ssh_config.get("user", "cluster")
        ssh_cmd = ["ssh", f"{user}@{host}", f"bash -lc '{cmd}'"]
        try:
            result = subprocess.run(
                ssh_cmd, capture_output=True, text=True, timeout=timeout
            )
            return CommandResult(
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(cmd=cmd, stdout="", stderr="TIMEOUT", exit_code=-1)
        except Exception as e:
            return CommandResult(cmd=cmd, stdout="", stderr=str(e), exit_code=-1)

    def _run_local(self, cmd: str, timeout: int) -> CommandResult:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return CommandResult(
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(cmd=cmd, stdout="", stderr="TIMEOUT", exit_code=-1)
        except Exception as e:
            return CommandResult(cmd=cmd, stdout="", stderr=str(e), exit_code=-1)

    def _run_mock(self, cmd: str) -> CommandResult:
        """Return canned responses for testing without a real cluster."""
        mock_responses = {
            "sinfo": (
                "PARTITION AVAIL TIMELIMIT NODES STATE  NODELIST\n"
                "batch*    up    infinite  3     idle   cn[01-03]\n"
                "batch*    up    infinite  1     drain  cn04\n"
            ),
            "squeue": (
                "JOBID PARTITION NAME     USER     ST TIME  NODES NODELIST(REASON)\n"
                "101   batch     test.sh  cluster  R  0:30  1     cn01\n"
                "102   batch     train.py cluster  PD 0:00  2     (Resources)\n"
            ),
            "scontrol show job 102": (
                "JobId=102 JobName=train.py\n"
                "UserId=cluster(1000) GroupId=cluster(1000)\n"
                "JobState=PENDING Reason=Resources\n"
                "NumNodes=2 NumCPUs=2\n"
                "Partition=batch\n"
                "SubmitTime=2025-04-10T10:00:00\n"
            ),
        }

        # Match by prefix
        for key, response in mock_responses.items():
            if cmd.strip().startswith(key):
                return CommandResult(cmd=cmd, stdout=response, stderr="", exit_code=0)

        return CommandResult(
            cmd=cmd, stdout="(mock: no canned response)", stderr="", exit_code=0
        )
