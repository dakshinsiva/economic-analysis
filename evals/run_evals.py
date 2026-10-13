"""Run the eval cases through the Stage 2 graph and score them.

    uv run python evals/run_evals.py              # local table + evals/results-<date>.json
    uv run python evals/run_evals.py --langsmith  # also upload dataset + run a LangSmith experiment

Scores per case (all 0..1):
  series_coverage   fraction of expected series present in the plan's tool args
  tools_ok          expected tools present and forbidden tools absent
  citations_grounded 1 if the deterministic citation check finds no issue in the final draft
  critic_approved   1 if the critic approved the final draft
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from econ_agent import nodes  # noqa: E402
from econ_agent.config import get_settings  # noqa: E402
from econ_agent.graph import build_graph_v2  # noqa: E402
from econ_agent.logging import setup_logging  # noqa: E402

CASES = Path(__file__).parent / "cases.yaml"


def run_case(question: str) -> dict:
    """Fresh graph per case: no cross-case memory, no checkpoint reuse."""
    g = build_graph_v2(InMemorySaver(), store=InMemoryStore())
    cfg = {"configurable": {"thread_id": "eval"}}
    t0 = time.perf_counter()
    g.invoke({"messages": [HumanMessage(question)]}, cfg)
    out = g.invoke(Command(resume="approve"), cfg)
    return {
        "plan": out["plan"], "evidence": out["evidence"], "draft": out["draft"],
        "critique": out["critique"], "revisions": out["revisions"],
        "answer": out["messages"][-1].content, "latency_s": round(time.perf_counter() - t0, 1),
    }


def score(case: dict, run: dict) -> dict[str, float]:
    args_blob = json.dumps([s["args"] for s in run["plan"]["steps"]]).upper()
    tools = [s["tool"] for s in run["plan"]["steps"]]
    exp = case.get("expected_series") or []
    cov = sum(sid.upper() in args_blob for sid in exp) / len(exp) if exp else 1.0
    tools_ok = all(t in tools for t in case.get("expect_tools", [])) and \
        not any(t in tools for t in case.get("forbid_tools", []))
    grounded = not nodes._deterministic_checks(run["draft"], run["evidence"])
    return {"series_coverage": round(cov, 2), "tools_ok": float(tools_ok),
            "citations_grounded": float(grounded), "critic_approved": float(run["critique"]["approved"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langsmith", action="store_true", help="upload dataset and run a LangSmith experiment")
    ap.add_argument("--only", help="run a single case id")
    a = ap.parse_args()

    s = get_settings()
    setup_logging(s.log_dir, "evals", s.log_level)
    cases = yaml.safe_load(CASES.read_text())
    if a.only:
        cases = [c for c in cases if c["id"] == a.only]

    results = []
    for c in cases:
        run = run_case(c["question"])
        sc = score(c, run)
        results.append({"id": c["id"], **sc, "revisions": run["revisions"], "latency_s": run["latency_s"],
                        "tools": [st["tool"] for st in run["plan"]["steps"]], "answer": run["answer"]})
        flags = " ".join(f"{k}={v:g}" for k, v in sc.items())
        print(f"{c['id']:20} {flags}  rev={run['revisions']} {run['latency_s']}s  tools={results[-1]['tools']}")

    keys = ["series_coverage", "tools_ok", "citations_grounded", "critic_approved"]
    print("\nMEAN " + "  ".join(f"{k}={sum(r[k] for r in results) / len(results):.2f}" for k in keys))
    out = Path(__file__).parent / f"results-{date.today().isoformat()}.json"
    out.write_text(json.dumps(results, indent=1))
    print(f"wrote {out}")

    if a.langsmith:
        from langsmith import Client, evaluate

        client = Client()
        name = "econ-agent-cases"
        ds = next(iter(client.list_datasets(dataset_name=name)), None) or client.create_dataset(name)
        existing = {e.inputs["question"] for e in client.list_examples(dataset_id=ds.id)}
        new = [c for c in cases if c["question"] not in existing]
        if new:
            client.create_examples(dataset_id=ds.id,
                                   inputs=[{"question": c["question"]} for c in new],
                                   outputs=[{k: c.get(k, []) for k in ("expected_series", "expect_tools", "forbid_tools")}
                                            for c in new])
        by_q = {c["question"]: c for c in cases}

        def target(inputs: dict) -> dict:
            return run_case(inputs["question"])

        def make_eval(key):
            def _e(inputs, outputs, reference_outputs):
                return {"key": key, "score": score(by_q[inputs["question"]], outputs)[key]}
            _e.__name__ = key
            return _e

        evaluate(target, data=name, evaluators=[make_eval(k) for k in keys],
                 experiment_prefix="econ-agent-v2", max_concurrency=1)


if __name__ == "__main__":
    main()
