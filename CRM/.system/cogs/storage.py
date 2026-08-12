from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
import json, os, shutil, uuid

STAGES = ["New","Qualified","Proposal","Negotiation","Won","Lost"]
STAGE_DIR = {s: f"Deals/Stage-{s}" for s in STAGES}

@dataclass
class FileChange:
    relpath: str
    before: str | None
    after: str | None
    operation: str = "write"

@dataclass
class Diff:
    action: str
    changes: list[FileChange] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

@dataclass
class StagingResult:
    staging_id: str
    path: str
    diff: Diff

@dataclass
class ActionResult:
    ok: bool
    intent: str
    message: str
    data: dict = field(default_factory=dict)
    layout: dict | None = None
    violations: list[str] = field(default_factory=list)
    hitl_required: bool = False

class CRMStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.staging = self.root / '.staging'
        self.staging.mkdir(parents=True, exist_ok=True)
        # Required human-facing report roots. Existing content is never replaced.
        (self.root / 'Reports').mkdir(parents=True, exist_ok=True)
        (self.root / 'Reports' / 'Internal').mkdir(parents=True, exist_ok=True)

    @staticmethod
    def parse_record(text: str) -> tuple[dict, str]:
        if not text.startswith('---\n'):
            raise ValueError('record missing frontmatter')
        _, front, body = text.split('---\n', 2)
        meta = json.loads(front.strip())
        return meta, body.lstrip('\n')

    @staticmethod
    def dump_record(meta: dict, body: str) -> str:
        return '---\n' + json.dumps(meta, separators=(',', ':'), ensure_ascii=False) + '\n---\n' + body.lstrip('\n')

    def read_text(self, relpath: str) -> str | None:
        p = self.root / relpath
        return p.read_text(encoding='utf-8') if p.exists() else None

    def read_record(self, relpath: str) -> tuple[dict, str]:
        text = self.read_text(relpath)
        if text is None: raise FileNotFoundError(relpath)
        return self.parse_record(text)

    def iter_records(self, folders=None):
        folders = folders or ['Contacts','Companies','Deals','Tasks']
        for folder in folders:
            base=self.root/folder
            if not base.exists(): continue
            for p in base.rglob('*.md'):
                try:
                    meta, body=self.parse_record(p.read_text(encoding='utf-8'))
                    yield p.relative_to(self.root).as_posix(), meta, body
                except Exception:
                    continue

    def find_by_id(self, rid: str):
        for rel, meta, body in self.iter_records():
            if meta.get('id') == rid: return rel, meta, body
        return None

    def new_id(self, prefix): return f"{prefix}-{uuid.uuid4().hex[:10]}"
    def now(self): return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')

    def stage_diff(self, diff: Diff) -> StagingResult:
        sid = uuid.uuid4().hex
        base = self.staging / sid
        for ch in diff.changes:
            p=base/'files'/ch.relpath
            if ch.after is not None:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(ch.after, encoding='utf-8')
        (base/'diff.json').parent.mkdir(parents=True, exist_ok=True)
        (base/'diff.json').write_text(json.dumps({'action':diff.action,'metadata':diff.metadata,'changes':[c.__dict__ for c in diff.changes]}, indent=2), encoding='utf-8')
        return StagingResult(sid, str(base), diff)

    def commit(self, staged: StagingResult):
        backup = Path(staged.path)/'backup'
        applied=[]
        try:
            for ch in staged.diff.changes:
                dst=self.root/ch.relpath
                bkp=backup/ch.relpath
                if dst.exists():
                    bkp.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst,bkp)
                if ch.after is None:
                    if dst.exists(): dst.unlink()
                else:
                    src=Path(staged.path)/'files'/ch.relpath
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp=dst.with_name(dst.name+'.commit-tmp')
                    shutil.copy2(src,tmp)
                    os.replace(tmp,dst)
                applied.append((dst,bkp,ch.before))
        except Exception:
            for dst,bkp,before in reversed(applied):
                if bkp.exists():
                    dst.parent.mkdir(parents=True,exist_ok=True); os.replace(bkp,dst)
                elif before is None and dst.exists(): dst.unlink()
            raise
        return True

    def remove_staging(self, sid):
        shutil.rmtree(self.staging/sid, ignore_errors=True)
