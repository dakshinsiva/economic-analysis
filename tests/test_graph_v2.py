"""Stage 2 graph tests with scripted planner/analyst/critic. No network, no keys.

Pattern: monkeypatch the three LLM factories in nodes.py with stand-ins that
return canned structured objects, then assert on routing and state.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from macrodesk import nodes
from macrodesk.graph import build_graph_v2
from macrodesk.state import Critique, Evidence, Plan, Step


class Canned:
    def __init__(self, *outs):
        self.outs, self.calls = list(outs), []

    def invoke(self, prompt):
        self.calls.append(prompt)
        return self.outs.pop(0) if len(self.outs) > 1 else self.outs[0]

    def stream(self, prompt):  # the analyst node streams; yield the canned message as one chunk
        yield self.invoke(prompt)


PLAN = Plan(goal="quits?", steps=[Step(tool="get_series", args={"series_id": "JTSQUR", "last_n": 3}, why="latest")])
CFG = {"configurable": {"thread_id": "t"}}


def _wire(monkeypatch, planner, analyst, critic):
    monkeypatch.setattr(nodes, "planner_llm", lambda: planner)
    monkeypatch.setattr(nodes, "analyst_llm", lambda: analyst)
    monkeypatch.setattr(nodes, "critic_llm", lambda: critic)


def test_pauses_for_review_then_runs_to_end_on_approve(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("Quits 1.9% (JTSQUR, 2026-08-01).")),
          Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    out = g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    assert "__interrupt__" in out
    assert out["__interrupt__"][0].value["steps"][0]["tool"] == "get_series"
    assert g.get_state(CFG).next == ("review",)
    assert fake_fred.calls == []  # nothing fetched before approval

    out = g.invoke(Command(resume="approve"), CFG)
    assert fake_fred.calls[0][:2] == ("get_series", "JTSQUR")
    assert out["evidence"][0]["ok"] and out["critique"]["approved"]
    assert out["messages"][-1].content.startswith("Quits 1.9%")
    assert g.get_state(CFG).next == ()


def test_feedback_at_review_replans(monkeypatch, fake_fred):
    plan2 = Plan(goal="quits 5y", steps=[Step(tool="get_series", args={"series_id": "JTSQUR", "start": "2021-01-01"}, why="hist")])
    planner = Canned(PLAN, plan2)
    _wire(monkeypatch, planner, Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    out = g.invoke(Command(resume="use five years of history"), CFG)
    # second interrupt with the revised plan
    assert out["__interrupt__"][0].value["steps"][0]["args"]["start"] == "2021-01-01"
    assert "five years" in str(planner.calls[1][-1].content)
    g.invoke(Command(resume="approve"), CFG)
    assert fake_fred.calls[0][2] == "2021-01-01"


def test_critic_bounces_unsupported_claim_then_accepts(monkeypatch, fake_fred):
    analyst = Canned(AIMessage("Quits peaked near 3.0% in 2022 (JTSQUR, 2022-04-01)."),
                     AIMessage("Quits 1.9% (JTSQUR, 2026-08-01)."))
    critic = Canned(Critique(approved=False, issues=["'peaked near 3.0% in 2022' not in evidence"]),
                    Critique(approved=True))
    _wire(monkeypatch, Canned(PLAN), analyst, critic)
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    out = g.invoke(Command(resume="approve"), CFG)
    assert out["revisions"] == 2 and out["critique"]["approved"]
    assert "peaked" in str(analyst.calls[1][0].content)  # critique fed back into analyst prompt
    assert out["messages"][-1].content == "Quits 1.9% (JTSQUR, 2026-08-01)."


def test_revision_cap_finalizes_with_reviewer_note(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("bad (JTSQUR, 2026-08-01)")),
          Canned(Critique(approved=False, issues=["still wrong"])))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("q")]}, CFG)
    out = g.invoke(Command(resume="approve"), CFG)
    assert out["revisions"] == nodes.MAX_REVISIONS
    assert "Reviewer note" in out["messages"][-1].content


def test_deterministic_citation_check():
    ev = [Evidence(tool="get_series", args={}, result="JTSQUR ... 2026-08-01  1.90", ok=True).model_dump()]
    issues = nodes._deterministic_checks("x (JTSQUR, 2026-08-01) y (UNRATE, 2026-09-01) z (JTSQUR, 2019-01-01)", ev)
    assert len(issues) == 2 and any("UNRATE" in i for i in issues) and any("2019-01-01" in i for i in issues)


def test_fetch_records_tool_errors_without_crashing(fake_fred):
    plan = Plan(goal="g", steps=[Step(tool="get_series", args={"series_id": "BOGUS"}, why="w"),
                                 Step(tool="get_series", args={"series_id": "JTSQUR"}, why="w")])
    out = nodes.fetch({"plan": plan.model_dump()})
    assert [e["ok"] for e in out["evidence"]] == [False, True]


def test_review_feedback_is_remembered_and_recalled_next_thread(monkeypatch, fake_fred):
    from langgraph.store.memory import InMemoryStore
    from macrodesk.memory import recall_feedback

    planner = Canned(PLAN)
    _wire(monkeypatch, planner, Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    store = InMemoryStore()
    g = build_graph_v2(InMemorySaver(), store=store)

    g.invoke({"messages": [HumanMessage("q")]}, CFG)
    g.invoke(Command(resume="always use 10 years of history"), CFG)  # feedback -> remembered
    assert recall_feedback(store) == ["always use 10 years of history"]

    cfg2 = {"configurable": {"thread_id": "t2"}}
    g.invoke({"messages": [HumanMessage("another question")]}, cfg2)
    system_prompt = str(planner.calls[-1][0].content)
    assert "always use 10 years of history" in system_prompt  # new thread, memory applied


def test_fetch_adds_chart_payload_for_plot_steps(fake_fred):
    plan = Plan(goal="g", steps=[Step(tool="plot_series", args={"series_ids": ["JTSQUR"], "title": "q"}, why="w")])
    out = nodes.fetch({"plan": plan.model_dump()})
    assert out["evidence"][0]["ok"]
    assert out["charts"][0]["panels"][0]["id"] == "JTSQUR"
    assert out["charts"][0]["panels"][0]["points"][-1]["d"] == "2026-08-01"


# ---------------------------------------------------------------- numeric grounding
def _ev(text):
    return [Evidence(tool="get_series", args={}, result=text, ok=True).model_dump()]


def test_numeric_check_passes_evidence_numbers_scales_and_derivations():
    ev = _ev("JTSJOL [Thousands, SA]\n2025-08-01  6,919.00\n2026-08-01  7,079.00\nmax 12,301.00 min 6,550.00")
    draft = ("Openings were 7,079 thousand (about 7.1 million) in August 2026, up 160 from a year earlier (+2.3%), "
             "a decline of 529,000 since the 6,550 low in reverse, and 42% below the 12,301 peak; "
             "5 of the 6 readings were above 7,000.")
    assert nodes._numeric_checks(draft, ev) == []


def test_numeric_check_flags_unsupported_number_and_unit_error():
    ev = _ev("JTSJOL [Thousands, SA]\n2026-08-01  7,079.00\nmean 7,437.97")
    issues = nodes._numeric_checks("The mean is 7,437,970 thousand and openings peaked near 12 million in 2022.", ev)
    assert any("Unit error" in i for i in issues)
    assert any("12 million" in i or "number 12" in i for i in issues)


def test_numeric_check_allows_numbers_from_the_question():
    ev = _ev("PCEPILFE yoy 3.01")
    assert nodes._numeric_checks("Core PCE is 3.01%, above the 2% target.", ev, question="Is core PCE above the 2% target?") == []


def test_numeric_check_catches_critic_bounce_end_to_end(monkeypatch, fake_fred):
    analyst = Canned(AIMessage("Quits rate is 1.9% (JTSQUR, 2026-08-01); openings peaked at 12,301 thousand."),
                     AIMessage("Quits rate is 1.9% (JTSQUR, 2026-08-01)."))
    _wire(monkeypatch, Canned(PLAN), analyst, Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    out = g.invoke(Command(resume="approve"), CFG)
    assert out["revisions"] == 2 and out["critique"]["approved"]  # deterministic check bounced the first draft


# ---------------------------------------------------------------- editable plan, concurrency, thread context
def test_review_accepts_an_edited_plan(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("ok (JTSQUR, 2026-08-01)")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("q")]}, CFG)
    edited = Plan(goal="edited", steps=[Step(tool="get_series", args={"series_id": "JTSQUR", "start": "2021-01-01"}, why="w")])
    out = g.invoke(Command(resume={"plan": edited.model_dump()}), CFG)
    assert out["plan"]["goal"] == "edited" and fake_fred.calls[0][2] == "2021-01-01"


def test_fetch_runs_steps_concurrently_in_plan_order(fake_fred):
    plan = Plan(goal="g", steps=[Step(tool="get_series", args={"series_id": s}, why="w") for s in ("JTSJOL", "BOGUS", "JTSQUR", "UNRATE")])
    out = nodes.fetch({"plan": plan.model_dump()})
    assert [e["args"]["series_id"] for e in out["evidence"]] == ["JTSJOL", "BOGUS", "JTSQUR", "UNRATE"]
    assert [e["ok"] for e in out["evidence"]] == [True, False, True, True]


def test_planner_sees_earlier_turns(monkeypatch, fake_fred):
    planner = Canned(PLAN)
    _wire(monkeypatch, planner, Canned(AIMessage("first answer")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("first question")]}, CFG); g.invoke(Command(resume="approve"), CFG)
    g.invoke({"messages": [HumanMessage("and compared with 2019?")]}, CFG)
    system = str(planner.calls[-1][0].content)
    assert "Earlier in this conversation" in system and "first question" in system and "first answer" in system


def test_planner_retries_when_step_args_are_invalid(monkeypatch, fake_fred):
    bad = Plan(goal="g", steps=[Step(tool="compare_to_prepandemic", args={}, why="missing series")])
    good = Plan(goal="g", steps=[Step(tool="compare_to_prepandemic", args={"series_id": "JTSQUR"}, why="fixed")])
    planner = Canned(bad, good)
    _wire(monkeypatch, planner, Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    out = g.invoke({"messages": [HumanMessage("q")]}, CFG)
    assert out["plan"]["steps"][0]["args"] == {"series_id": "JTSQUR"}
    assert "invalid arguments" in str(planner.calls[1][-1].content)


def test_prior_evidence_carries_into_follow_up(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("Quits 1.9% (JTSQUR, 2026-08-01).")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG); g.invoke(Command(resume="approve"), CFG)
    follow = g.invoke({"messages": [HumanMessage("and vs last year?")]}, CFG)
    assert follow["evidence"] == [] and follow["prior_evidence"][0]["prior"] and follow["prior_evidence"][0]["tool"] == "get_series"
    assert "JTSQUR" in nodes._format_evidence(nodes._all_evidence(follow))


def test_deterministic_layer_overrules_model_objections_about_verified_numbers():
    ev = _ev("PCEPILFE yoy\n2026-03-01  3.11\n2026-04-01  3.08\n2026-05-01  3.16\n2026-06-01  3.04\n2026-07-01  2.98\n2026-08-01  3.01")
    draft = "Five of the six readings are at or above 3% and the range is 2.98% to 3.16% (PCEPILFE, 2026-08-01)."
    verified = nodes._verified_numbers(draft, ev, "")
    kept, overruled = nodes._overrule(["'range is 2.98% to 3.16%' is a derived claim", "The draft asserts a rising trend that the data do not show"], verified)
    assert overruled == ["'range is 2.98% to 3.16%' is a derived claim"]
    assert kept == ["The draft asserts a rising trend that the data do not show"]


def test_overrule_examines_only_the_quoted_draft_sentence_and_drops_self_resolved():
    ev = _ev("A191RL1Q225SBEA [Percent, SAAR]\n2026-04-01  2.20\nchange -0.30 vs 1 obs ago")
    draft = "Real GDP grew 2.2% in Q1 2026, down from 2.5% the prior quarter (A191RL1Q225SBEA, 2026-04-01)."
    verified = nodes._verified_numbers(draft, ev, "")
    assert "2.5" in verified  # a sum of two evidence numbers
    issues = ['"down from 2.5% the prior quarter" — the evidence shows 2.20 and -0.30; the prior quarter is derived as 2.20 + 0.30 = 2.50, which',
              '"Initial claims: 197 thousand" — 197,000 equals 197 thousand. No issue.',
              '"the weakest reading since the COVID trough" — the evidence does not support this claim']
    kept, overruled = nodes._overrule(issues, verified)
    assert kept == [issues[2]] and len(overruled) == 2
