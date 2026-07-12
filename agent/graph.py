"""LangGraph state machine: plan -> call_tool -> evaluate -> (loop | finalize).

- plan: LLM picks one tool + input to gather the next piece of evidence.
- call_tool: runs it via tools.registry.call_tool (which retries once and
  never raises), and appends a ReasoningStep to the trace.
- evaluate: LLM decides whether there's enough evidence to finalize, or
  whether to loop back to plan. Forced to finalize once max_iterations is
  hit, regardless of what the LLM would have chosen.
- finalize: LLM synthesizes the structured Diagnosis from the trace. If the
  cap was hit without any successful tool call, confidence is capped and
  insufficient_evidence is set so the API response is honest about it.
"""
from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from agent.llm import get_chat_model
from agent.schemas import AgentResult, Diagnosis, ReasoningStep
from agent.state import AgentState
from config import settings
from tools.registry import call_tool
from tools.schemas import ToolName

TOOL_DESCRIPTIONS = """- log_search(keyword?, service?, start_time?, end_time?, limit?): search incident logs by keyword, service name, and/or time range.
- web_search(query): look up known public issues matching an error pattern (mocked known-issue index).
- code_exec(code, timeout_seconds?): run a short Python snippet to validate a calculation or hypothesis.
- runbook_retrieval(query, top_k?): retrieve similar past-incident runbooks with root cause and resolution."""


class ToolCallPlan(BaseModel):
    thought: str = Field(description="Brief reasoning for why this tool/input was chosen next")
    tool_name: ToolName
    tool_input: dict[str, Any] = Field(description="Arguments for the chosen tool, matching its input schema")


class EvaluateDecision(BaseModel):
    thought: str
    decision: Literal["continue", "finalize"]
    confidence: float = Field(ge=0.0, le=1.0)


def _summarize_trace(trace: list[dict[str, Any]]) -> str:
    if not trace:
        return "(none yet)"
    lines = []
    for step in trace:
        status = "FAILED" if step.get("tool_failed") else "ok"
        lines.append(
            f"Step {step['step']} [{status}] thought={step['thought']!r} "
            f"tool={step.get('tool_called')} input={step.get('tool_input')} "
            f"result={step.get('tool_result')}"
        )
    return "\n".join(lines)


def plan_node(state: AgentState) -> dict[str, Any]:
    llm = get_chat_model().with_structured_output(ToolCallPlan)
    plan = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an SRE triage agent diagnosing a production incident. "
                    f"Available tools:\n{TOOL_DESCRIPTIONS}\n"
                    "Pick exactly one tool to call next that will gather the most useful new "
                    "evidence. Don't repeat a call you've already made with the same input."
                )
            ),
            HumanMessage(
                content=(
                    f"Incident: {state['incident_description']}\n\n"
                    f"Evidence gathered so far:\n{_summarize_trace(state['reasoning_trace'])}"
                )
            ),
        ]
    )
    return {"pending_tool_call": plan.model_dump()}


def call_tool_node(state: AgentState) -> dict[str, Any]:
    pending = state["pending_tool_call"]
    result = call_tool(pending["tool_name"], pending["tool_input"])
    step = ReasoningStep(
        step=state["iteration"] + 1,
        thought=pending["thought"],
        tool_called=pending["tool_name"],
        tool_input=pending["tool_input"],
        tool_result=result,
        tool_failed=not result.get("success", False),
    )
    return {
        "reasoning_trace": state["reasoning_trace"] + [step.model_dump()],
        "iteration": state["iteration"] + 1,
        "pending_tool_call": None,
    }


def evaluate_node(state: AgentState) -> dict[str, Any]:
    if state["iteration"] >= state["max_iterations"]:
        return {"route": "finalize", "forced_by_cap": True}

    llm = get_chat_model().with_structured_output(EvaluateDecision)
    decision = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are deciding whether enough evidence has been gathered to diagnose "
                    "this incident's root cause with reasonable confidence, or whether another "
                    "tool call is needed. Prefer finalizing once you have converging evidence "
                    "(e.g. matching logs and a runbook) rather than exhausting all iterations."
                )
            ),
            HumanMessage(
                content=(
                    f"Incident: {state['incident_description']}\n\n"
                    f"Evidence gathered so far:\n{_summarize_trace(state['reasoning_trace'])}"
                )
            ),
        ]
    )
    return {"route": decision.decision, "forced_by_cap": False}


def finalize_node(state: AgentState) -> dict[str, Any]:
    trace = state["reasoning_trace"]
    forced_by_cap = state["forced_by_cap"]

    llm = get_chat_model().with_structured_output(Diagnosis)
    diagnosis = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Synthesize a final incident diagnosis from the evidence trail below. Cite "
                    "specific evidence (log entries, runbook doc ids) in evidence_trail. If the "
                    "evidence is thin or contradictory, say so honestly with lower confidence."
                )
            ),
            HumanMessage(
                content=(
                    f"Incident: {state['incident_description']}\n\n"
                    f"Evidence gathered:\n{_summarize_trace(trace)}"
                )
            ),
        ]
    )
    result = diagnosis.model_dump()
    if forced_by_cap:
        result["confidence"] = min(result["confidence"], 0.3)
        result["insufficient_evidence"] = True
    return {"diagnosis": result}


def _route_after_evaluate(state: AgentState) -> Literal["plan", "finalize"]:
    if state["iteration"] >= state["max_iterations"]:
        return "finalize"
    return "finalize" if state["route"] == "finalize" else "plan"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("call_tool", call_tool_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "call_tool")
    graph.add_edge("call_tool", "evaluate")
    graph.add_conditional_edges("evaluate", _route_after_evaluate, {"plan": "plan", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    return graph.compile()


def run_agent(incident_description: str, max_iterations: int | None = None) -> AgentResult:
    app = build_graph()
    initial_state: AgentState = {
        "incident_description": incident_description,
        "reasoning_trace": [],
        "iteration": 0,
        "max_iterations": max_iterations or settings.max_agent_iterations,
        "pending_tool_call": None,
        "diagnosis": None,
        "route": None,
        "forced_by_cap": False,
    }
    final_state = app.invoke(initial_state)
    return AgentResult(
        diagnosis=Diagnosis(**final_state["diagnosis"]),
        reasoning_trace=[ReasoningStep(**step) for step in final_state["reasoning_trace"]],
        iterations_used=final_state["iteration"],
    )