from pathlib import Path
import json, re, sys
SYSTEM=Path(__file__).resolve().parent; ROOT=SYSTEM.parent
sys.path.insert(0,str(SYSTEM/'orchestrator')); from conductor import Conductor
def run_onboarding(name=None, cleanup='07:00', nightly_start='22:00', nightly_end='01:00'):
    settings_path=ROOT/'.system/config/settings.yaml'; s=json.loads(settings_path.read_text());
    if name: s['user_name']=name
    s['hours'].update({'daily_cleanup':cleanup,'nightly_development_start':nightly_start,'nightly_development_end':nightly_end}); s['onboarding_complete']=True; settings_path.write_text(json.dumps(s,indent=2)+'\n')
    c=Conductor(ROOT)
    company = next((m for _,m,_ in c.store.iter_records(['Companies'])), None)
    if company:
        slug = re.sub(r'[^a-z0-9]+', '-', company.get('name','client').lower()).strip('-') or company['id']
        report_dir = ROOT/'Reports'/slug; report_dir.mkdir(parents=True, exist_ok=True)
        demo = report_dir/'onboarding-demo.md'
        if not demo.exists():
            demo.write_text('---\n'+json.dumps({'company_id':company['id'],'report_type':'onboarding_demo','generated_at':c.store.now()},separators=(',',':'))+'\n---\n# '+company.get('name','Client')+'\n\nThis sample report demonstrates where client-specific generated reports are stored.\n')
    c.refresh_session_files(); return s
