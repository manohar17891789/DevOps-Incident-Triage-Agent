"""Runs a short Python snippet in an isolated subprocess with a timeout.

Used by the agent to validate hypotheses (e.g. parse a timestamp, compute a
rate, reproduce a small calculation) rather than to execute arbitrary
production code. No filesystem/network sandboxing beyond a fresh subprocess
and a wall-clock timeout -- see README "what I'd improve" for hardening notes.
"""
import subprocess
import sys

from tools.schemas import CodeExecInput, CodeExecOutput


def run_code_exec(input: CodeExecInput) -> CodeExecOutput:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", input.code],
            capture_output=True,
            text=True,
            timeout=input.timeout_seconds,
        )
        return CodeExecOutput(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return CodeExecOutput(
            success=False,
            timed_out=True,
            error=f"Execution exceeded {input.timeout_seconds}s timeout",
        )
