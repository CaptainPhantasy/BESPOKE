from dataclasses import dataclass
from pathlib import Path
import ast

@dataclass
class AgentDecision:
    role: str
    summary: str
    payload: dict

class OrchestraAgent:
    def analyze(self, evidence):
        if evidence.get("frequent_intents"):
            intent = evidence["frequent_intents"][0]
            return AgentDecision("orchestra", f"Improve frequent intent {intent}", {"target_intent": intent})
        return AgentDecision("orchestra", "Add a useful pipeline report intent.", {"target_intent": "pipeline_report"})

class CodingAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def build(self, decision, evidence):
        if self.llm:
            return self.llm(decision, evidence)
        code = '''from pathlib import Path
import sys

def execute(root, params):
    root = Path(root)
    sys.path.insert(0, str(root / ".system/cogs"))
    from storage import CRMStore
    store = CRMStore(root)
    rows = []
    total = 0.0
    for rel, meta, body in store.iter_records(["Deals"]):
        if meta.get("stage") not in {"Won", "Lost"}:
            rows.append(meta)
            total += float(meta.get("value", 0) or 0)
    out = root / "Reports" / f"pipeline-summary-{store.now()[:10]}.md"
    lines = ["# Pipeline Summary", "", f"Open deals: {len(rows)}", f"Open value: ${total:,.2f}", "", "| Deal | Stage | Value |", "|---|---|---:|"]
    lines += [f"| {d.get('name','')} | {d.get('stage','')} | ${float(d.get('value',0) or 0):,.2f} |" for d in rows]
    out.write_text("\\n".join(lines) + "\\n")
    return {"report": str(out.relative_to(root)), "open_deals": len(rows), "open_value": total}
'''
        return {
            "name": "Pipeline Summary Report",
            "description": "Adds a generated pipeline summary report intent.",
            "intent_patch": {"pipeline_report": ["plugin:report_worker:execute"]},
            "files": {".system/cogs/workers/report_worker.py": code},
        }

class VerifyAgent:
    def verify(self, bundle):
        problems = []
        if not bundle.get("name"):
            problems.append("missing name")
        if not isinstance(bundle.get("files"), dict) or not bundle["files"]:
            problems.append("missing files")
        for name, content in bundle.get("files", {}).items():
            if name.startswith("/") or ".." in Path(name).parts:
                problems.append(f"unsafe path: {name}")
            if name.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as exc:
                    problems.append(f"{name}: syntax error: {exc}")
        return {"ok": not problems, "violations": problems}
