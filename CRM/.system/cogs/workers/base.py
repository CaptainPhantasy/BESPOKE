from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import CRMStore, Diff, StagingResult

class BaseWorker(ABC):
    def __init__(self, root): self.store=CRMStore(root); self._staged={}
    @abstractmethod
    def preview(self, params) -> Diff: ...
    def dry_run(self, params) -> StagingResult:
        diff=self.preview(params); result=self.store.stage_diff(diff); self._staged[result.staging_id]=result; return result
    def rollback(self, staging_id) -> None:
        self.store.remove_staging(staging_id); self._staged.pop(staging_id,None)
