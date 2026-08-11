from __future__ import annotations
from pathlib import Path
from datetime import datetime, time
import argparse, json, shutil, sys, time as clock
from zoneinfo import ZoneInfo
SYSTEM=Path(__file__).resolve().parent; ROOT=SYSTEM.parent
sys.path.insert(0,str(SYSTEM/'orchestrator')); sys.path.insert(0,str(SYSTEM/'cogs'))
from conductor import Conductor
from orchestrator import NightlyOrchestrator
class Heartbeat:
    def __init__(self,root=ROOT):
        self.root=Path(root); self.config=json.loads((self.root/'.system/config/heartbeat.yaml').read_text()); self.settings=json.loads((self.root/'.system/config/settings.yaml').read_text()); self.conductor=Conductor(self.root); self.last_daily=None; self.last_nightly_date=None
    def tick(self):
        self.conductor.refresh_session_files(); light=self.conductor.verifier.run_full_audit(); tz=ZoneInfo(self.settings.get('timezone','UTC')); now=datetime.now(tz); actions=['scan_overdue_tasks','update_pipeline_snapshot','light_integrity_check']
        daily_time=self.settings['hours'].get('daily_cleanup','07:00')
        if now.strftime('%H:%M')==daily_time and self.last_daily!=now.date(): self.daily_cleanup(); self.last_daily=now.date(); actions.append('daily_cleanup')
        if self._inside_nightly(now) and self.last_nightly_date!=now.date():
            result=NightlyOrchestrator(self.root).run_nightly(); self.last_nightly_date=now.date(); actions.append('nightly_orchestration')
        return {'at':now.isoformat(),'actions':actions,'light_audit_ok':light['ok']}
    def daily_cleanup(self):
        audit=self.conductor.verifier.run_full_audit()
        self.rebuild_index()
        self.archive_completed_tasks()
        self.conductor.refresh_session_files()
        for p in (self.root/'.staging').iterdir():
            if p.is_dir() and (datetime.now().timestamp()-p.stat().st_mtime)>86400:
                shutil.rmtree(p,ignore_errors=True)
        return audit
    def rebuild_index(self):
        index={m.get('id'): rel for rel,m,b in self.conductor.store.iter_records() if m.get('id')}
        (self.root/'.system/index.json').write_text(json.dumps(index,indent=2)+'\n')
        return index
    def archive_completed_tasks(self):
        from datetime import timedelta
        archive=self.root/'Tasks/Archive'; archive.mkdir(parents=True,exist_ok=True)
        cutoff=datetime.now(ZoneInfo(self.settings.get('timezone','UTC')))-timedelta(days=30)
        moved=[]
        for rel,m,b in list(self.conductor.store.iter_records(['Tasks'])):
            if m.get('status')!='completed' or not m.get('completed_at'): continue
            try: done=datetime.fromisoformat(m['completed_at'])
            except Exception: continue
            if done < cutoff:
                src=self.root/rel; dst=archive/src.name; shutil.move(str(src),str(dst)); moved.append(src.name)
        return moved
    def _inside_nightly(self,now):
        s=self.settings['hours'].get('nightly_development_start','22:00'); e=self.settings['hours'].get('nightly_development_end','01:00')
        sm=int(s[:2])*60+int(s[3:]); em=int(e[:2])*60+int(e[3:]); m=now.hour*60+now.minute
        return (sm<=m<em) if sm<em else (m>=sm or m<em)
    def run(self,once=False):
        interval=max(1,int(self.config.get('interval_minutes',5)))*60
        while True:
            print(json.dumps(self.tick()),flush=True)
            if once:return
            clock.sleep(interval)
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--once',action='store_true'); args=ap.parse_args(); Heartbeat().run(args.once)
