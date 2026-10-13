"""Node functions for the Stage 2 graph.

Each node is a plain function: state in, partial state out. LLM access goes
through small factory functions (`planner_llm`, `analyst_llm`, `critic_llm`) so
tests can monkeypatch them with scripted stand-ins.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from econ_agent.models import make_model
from econ_agent.logging import log_event
from econ_agent.memory import recall_feedback, remember_feedback
from econ_agent.state import AgentState, Critique, Evidence, Plan
from econ_agent.tools import ALL_TOOLS

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
MAX_REVISIONS = 2


def _tool_catalog() -> str:
    return "\n".join(f"- {t.name}{t.args_schema.model_json_schema().get('properties', {}) if t.args_schema else ''}: "
                     f"{t.description.strip().splitlines()[0]}" for t in ALL_TOOLS)


def _last_user_text(state: AgentState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return m.text if isinstance(m.text, str) else str(m.content)
    return ""


# ---- LLM factories (monkeypatched in tests) ----------------------------------
def planner_llm():
    return make_model().with_structured_output(Plan)


def analyst_llm():
    return make_model()


def critic_llm():
    return make_model().with_structured_output(Critique)


# ---- nodes --------------------------------------------------------------------
PLANNER_SYSTEM = """You plan data retrieval for an economic analyst. Produce a short, concrete plan of tool calls
that will gather ALL the evidence needed to answer the question. Rules:
- Use series ids from the curated list when possible (JOLTS: JTSJOL JTSHIR JTSQUR JTSLDL; UNRATE PAYEMS ICSA;
  GDPC1 A191RL1Q225SBEA INDPRO; CPIAUCSL CPILFESL PCEPILFE; DGS3MO DGS2 DGS10 DGS30 T10Y2Y T10Y3M FEDFUNDS;
  UMCSENT HOUST RSAFS). Use search_fred only for something outside that list.
- If the user wants history or context (peaks, pre-pandemic levels), fetch a long enough window (start=YYYY-MM-DD)
  so that the analyst never has to rely on memory.
- Prefer compute_change for growth rates and yield_curve_snapshot for curve questions.
- Include plot_series only if the user asks for a chart/graph/plot.
{prefs}
Available tools:
{catalog}"""


def planner(state: AgentState, runtime: Runtime) -> dict[str, Any]:
    question = _last_user_text(state)
    feedback = state.get("plan_feedback")
    remembered = recall_feedback(runtime.store)
    prefs = ""
    if remembered:
        prefs = ("Feedback this user gave on earlier plans (apply when relevant to this question):\n"
                 + "\n".join(f"- {r}" for r in remembered))
    log_event("planner.recall", n_prefs=len(remembered))
    prompt = [SystemMessage(PLANNER_SYSTEM.format(catalog=_tool_catalog(), prefs=prefs)), HumanMessage(question)]
    if feedback and state.get("plan"):
        prompt.append(AIMessage(f"Previous plan: {Plan.model_validate(state['plan']).model_dump_json()}"))
        prompt.append(HumanMessage(f"Revise the plan with this feedback: {feedback}"))
    plan: Plan = planner_llm().invoke(prompt)
    log_event("planner.done", n_steps=len(plan.steps), tools=[s.tool for s in plan.steps], feedback=feedback)
    return {"plan": plan.model_dump(), "plan_feedback": None, "evidence": [], "draft": "", "critique": None,
            "revisions": 0}


def review(state: AgentState, runtime: Runtime) -> dict[str, Any]:
    """Human-in-the-loop. Pauses the graph; resume with Command(resume='approve') or free text feedback.
    Feedback is also written to long-term memory so future plans start from it."""
    plan = Plan.model_validate(state["plan"])
    decision = interrupt({
        "type": "plan_review",
        "goal": plan.goal,
        "steps": [s.model_dump() for s in plan.steps],
        "hint": "resume with 'approve' or with feedback text to replan",
    })
    if isinstance(decision, str) and decision.strip().lower() in ("", "approve", "y", "yes", "ok"):
        log_event("review.approved")
        return {"plan_feedback": None}
    log_event("review.feedback", feedback=decision)
    remember_feedback(runtime.store, str(decision))
    return {"plan_feedback": str(decision)}


def route_after_review(state: AgentState) -> str:
    return "planner" if state.get("plan_feedback") else "fetch"


def fetch(state: AgentState) -> dict[str, Any]:
    """Deterministic: execute the approved plan. No LLM involved."""
    evidence: list[dict[str, Any]] = []
    for step in Plan.model_validate(state["plan"]).steps:
        tool = TOOLS_BY_NAME[step.tool]
        try:
            result = tool.invoke(step.args)
            ok = not str(result).startswith("ERROR")
        except Exception as e:  # bad args etc. -> keep going, record it
            result, ok = f"ERROR: {type(e).__name__}: {e}", False
        evidence.append(Evidence(tool=step.tool, args=step.args, result=str(result), ok=ok).model_dump())
        log_event("fetch.step", tool=step.tool, args=step.args, ok=ok, chars=len(str(result)))
    return {"evidence": evidence}


ANALYST_SYSTEM = """You are an economic analyst. Write the answer to the user's question using ONLY the evidence
below. Hard rules:
- Every number, date, peak, average or comparison you state must appear in the evidence. If the evidence does not
  contain it, do not say it - say that it was not retrieved instead.
- Cite each figure as (SERIES_ID, YYYY-MM-DD). State units.
- Lead with the answer, then 3-6 evidence bullets, then caveats (release lags, revisions).
- If a chart was produced, give the user its file path.
{critique_block}
EVIDENCE:
{evidence}"""


def _format_evidence(ev: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"[{i}] {e['tool']}({e['args']})\n{e['result']}" for i, e in enumerate(ev, 1))


def analyst(state: AgentState) -> dict[str, Any]:
    critique = Critique.model_validate(state["critique"]) if state.get("critique") else None
    critique_block = ""
    if critique and not critique.approved:
        critique_block = ("A reviewer rejected your previous draft. Fix these issues (remove or re-source each claim):\n"
                          + "\n".join(f"- {i}" for i in critique.issues)
                          + f"\n\nPREVIOUS DRAFT:\n{state.get('draft', '')}\n")
    prompt = [SystemMessage(ANALYST_SYSTEM.format(critique_block=critique_block,
                                                  evidence=_format_evidence(state["evidence"]))),
              HumanMessage(_last_user_text(state))]
    msg = analyst_llm().invoke(prompt)
    draft = msg.text if isinstance(getattr(msg, "text", None), str) else str(getattr(msg, "content", msg))
    log_event("analyst.draft", chars=len(draft), revision=state.get("revisions", 0))
    return {"draft": draft}


CRITIC_SYSTEM = """You are a strict but fair fact-checker. Compare the DRAFT against the EVIDENCE.

FLAG a sentence only if it states a number, date, level, peak, average, range, or historical comparison that is
neither present in the evidence nor derivable from it by simple arithmetic.
  - Unsupported: "peaked near 12 million in 2022" when no 2022 data was fetched; a date or value that appears
    nowhere; a "series low" claim when the evidence shows a lower value; a unit error such as reporting a value
    given in thousands as if it were units (7,437.97 thousand is NOT 7,437,970 thousand).
  - Supported (do NOT flag): differences, percentage-point gaps vs a stated target, counts like "5 of the 6
    readings", min/max/mean quoted from the evidence's summary line, and qualitative interpretation.
When the evidence shows a window (e.g. "latest 6") treat "peak"/"low" claims as supported if the draft says
"in the window shown" or similar; flag them only if stated as all-time without qualification.

Output rules: `issues` must contain ONLY genuine problems, each quoting the offending sentence and saying what
the evidence actually shows. Never include an entry that says there is no issue. If `issues` is empty,
`approved` must be true; if it is non-empty, `approved` must be false. Double-check your own arithmetic
before flagging a number."""

CRITIC_USER = """EVIDENCE:
{evidence}

DRAFT:
{draft}"""

_CITE_RE = re.compile(r"\(([A-Z0-9]{3,20}),\s*(\d{4}-\d{2}-\d{2})\)")


def _deterministic_checks(draft: str, evidence: list[dict[str, Any]]) -> list[str]:
    """Cheap, non-LLM checks: cited series ids must appear in fetched evidence."""
    blob = "\n".join(e["result"] for e in evidence)
    issues = []
    for sid, d in set(_CITE_RE.findall(draft)):
        if sid not in blob:
            issues.append(f"Cites ({sid}, {d}) but no evidence for series {sid} was fetched.")
        elif d not in blob:
            issues.append(f"Cites ({sid}, {d}) but date {d} does not appear in the evidence.")
    return issues


def critic(state: AgentState) -> dict[str, Any]:
    issues = _deterministic_checks(state["draft"], state["evidence"])
    # Anthropic requires at least one non-system message (see debugging note 6).
    verdict: Critique = critic_llm().invoke([
        SystemMessage(CRITIC_SYSTEM),
        HumanMessage(CRITIC_USER.format(evidence=_format_evidence(state["evidence"]), draft=state["draft"])),
    ])
    issues += verdict.issues
    approved = verdict.approved and not issues
    log_event("critic.verdict", approved=approved, n_issues=len(issues), issues=issues)
    return {"critique": Critique(approved=approved, issues=issues).model_dump(),
            "revisions": state.get("revisions", 0) + 1}


def route_after_critic(state: AgentState) -> str:
    c = state.get("critique")
    if c and not c["approved"] and state.get("revisions", 0) < MAX_REVISIONS:
        return "analyst"
    return "finalize"


def finalize(state: AgentState) -> dict[str, Any]:
    text = state["draft"]
    c = state.get("critique")
    if c and not c["approved"]:
        text += ("\n\n_Reviewer note: this answer still had unresolved issues after "
                 f"{state.get('revisions', 0)} revisions: " + "; ".join(c["issues"]) + "_")
    return {"messages": [AIMessage(text)]}
