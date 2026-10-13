"""Measure the critic itself against labelled drafts.

    uv run python evals/run_critic_evals.py            # deterministic checks only (free, instant)
    uv run python evals/run_critic_evals.py --llm      # also the model critic (one call per case)

Reports precision/recall of "reject" for the deterministic layer, the model layer, and the
combination the graph actually uses.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macrodesk import nodes  # noqa: E402
from macrodesk.state import Critique, Evidence  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    cases = yaml.safe_load((Path(__file__).parent / "critic_cases.yaml").read_text())
    rows = []
    for c in cases:
        ev = [Evidence(tool="get_series", args={}, result=c["evidence"], ok=True).model_dump()]
        det = nodes._deterministic_checks(c["draft"], ev) + nodes._numeric_checks(c["draft"], ev, c.get("question", ""))
        row = {"id": c["id"], "truth": c["verdict"], "det_reject": bool(det), "det_issues": det}
        if a.llm:
            from langchain_core.messages import HumanMessage, SystemMessage
            v: Critique = nodes.critic_llm().invoke([SystemMessage(nodes.CRITIC_SYSTEM),
                                                     HumanMessage(nodes.CRITIC_USER.format(evidence=nodes._format_evidence(ev), draft=c["draft"]))])
            row["llm_reject"] = not v.approved or bool(v.issues)
            row["llm_issues"] = v.issues
            row["combined_reject"] = row["det_reject"] or row["llm_reject"]
        rows.append(row)
        mark = lambda k: ("REJECT" if row.get(k) else "approve") if k in row else "-"
        print(f"{c['id']:32} truth={c['verdict']:7} det={mark('det_reject'):7} llm={mark('llm_reject'):7} combined={mark('combined_reject')}")
        for i in det: print("      det:", i[:140])

    def prf(key: str) -> str:
        tp = sum(r[key] and r["truth"] == "reject" for r in rows if key in r)
        fp = sum(r[key] and r["truth"] == "approve" for r in rows if key in r)
        fn = sum((not r[key]) and r["truth"] == "reject" for r in rows if key in r)
        p = tp / (tp + fp) if tp + fp else 1.0; rc = tp / (tp + fn) if tp + fn else 1.0
        return f"precision {p:.2f} recall {rc:.2f} (tp={tp} fp={fp} fn={fn})"
    print("\ndeterministic:", prf("det_reject"))
    if a.llm:
        print("model:        ", prf("llm_reject"))
        print("combined:     ", prf("combined_reject"))
    out = Path(__file__).parent / f"critic-results-{date.today().isoformat()}.json"
    out.write_text(json.dumps(rows, indent=1)); print("wrote", out)


if __name__ == "__main__":
    main()
