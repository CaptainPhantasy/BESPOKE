from pathlib import Path
import json, sys
SYSTEM=Path(__file__).resolve().parent; ROOT=SYSTEM.parent
sys.path.insert(0,str(SYSTEM/'orchestrator')); from conductor import Conductor
def run_onboarding(name=None, cleanup='07:00', nightly_start='22:00', nightly_end='01:00'):
    settings_path=ROOT/'.system/config/settings.yaml'; s=json.loads(settings_path.read_text());
    if name: s['user_name']=name
    s['hours'].update({'daily_cleanup':cleanup,'nightly_development_start':nightly_start,'nightly_development_end':nightly_end}); s['onboarding_complete']=True; settings_path.write_text(json.dumps(s,indent=2)+'\n')
    c=Conductor(ROOT); c.refresh_session_files(); return s
