from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import os
import shutil
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import OrchestraAgent, CodingAgent, VerifyAgent
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cogs"))
from verifier import Verifier

class NightlyOrchestrator:
    def __init__(self, root, llm=None):
        self.root = Path(root)
        self.proposals = self.root / ".system/orchestrator/proposals"
        self.proposals.mkdir(parents=True, exist_ok=True)
        self.orchestra = OrchestraAgent()
        self.coder = CodingAgent(llm)
        self.verify_agent = VerifyAgent()

    def collect_evidence(self):
        counts = {}
        audit = self.root / ".system/audit.log"
        if audit.exists():
            for line in audit.read_text().splitlines():
                try:
                    item = json.loads(line)
                    counts[item.get("intent")] = counts.get(item.get("intent"), 0) + 1
                except Exception:
                    pass
        frequent = [k for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True) if k]
        return {"frequent_intents": frequent, "audit_counts": counts}

    def run_nightly(self):
        evidence = self.collect_evidence()
        decision = self.orchestra.analyze(evidence)
        bundle = self.coder.build(decision, evidence)
        verification = self.verify_agent.verify(bundle)
        if not verification["ok"]:
            return {"ok": False, "verification": verification}
        with tempfile.TemporaryDirectory() as td:
            mirror = Path(td) / "CRM"
            shutil.copytree(self.root, mirror, ignore=shutil.ignore_patterns(".staging", "proposals"))
            for rel, content in bundle["files"].items():
                target = mirror / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            audit = Verifier(mirror).run_full_audit()
            if not audit["ok"]:
                return {"ok": False, "verification": {"ok": False, "violations": audit["violations"]}}
        feature_id = "feature-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:5]
        out = self.proposals / feature_id
        out.mkdir(parents=True)
        for rel, content in bundle["files"].items():
            target = out / "files" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        manifest = {
            "id": feature_id,
            "name": bundle["name"],
            "description": bundle.get("description", ""),
            "status": "proposed",
            "created_at": datetime.now().astimezone().isoformat(),
            "decision": decision.__dict__,
            "verification": verification,
            "files": list(bundle["files"]),
            "intent_patch": bundle.get("intent_patch", {}),
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        with (self.root / ".system/session/autonomous_activity_log.md").open("a") as fh:
            fh.write(f"\n- Proposed **{bundle['name']}** ({feature_id}); not activated.\n")
        return {"ok": True, "feature_id": feature_id, "manifest": manifest}

    def activate_feature(self, feature_id):
        src = self.proposals / feature_id
        manifest = json.loads((src / "manifest.json").read_text())
        for rel in manifest.get("files", []):
            source = src / "files" / rel
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_target = target.with_name(target.name + ".feature-tmp")
            shutil.copy2(source, temp_target)
            os.replace(temp_target, target)
        if manifest.get("intent_patch"):
            cfg = self.root / ".system/config/intent_plans.yaml"
            plans = json.loads(cfg.read_text())
            plans.update(manifest["intent_patch"])
            temp_cfg = cfg.with_name(cfg.name + ".feature-tmp")
            temp_cfg.write_text(json.dumps(plans, indent=2) + "\n")
            os.replace(temp_cfg, cfg)
        manifest["status"] = "active"
        (src / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return {"feature_id": feature_id, "status": "active", "installed": manifest.get("files", []), "intents": list(manifest.get("intent_patch", {}))}
