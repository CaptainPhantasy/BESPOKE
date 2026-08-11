from __future__ import annotations
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import argparse, json, os, subprocess, sys, threading, webbrowser
ROOT=Path(__file__).resolve().parent; CRM=ROOT/'CRM'; SYSTEM=CRM/'.system'; sys.path.insert(0,str(SYSTEM/'orchestrator')); sys.path.insert(0,str(SYSTEM/'cogs'))
from conductor import Conductor
class Handler(SimpleHTTPRequestHandler):
    conductor=None
    def do_GET(self):
        if self.path=='/layout': return self._json(self.conductor.render_layout())
        if self.path.startswith('/images/'):
            name=Path(self.path).name; img=SYSTEM/'ui/images'/name
            if not img.exists(): self.send_error(404); return
            data=img.read_bytes(); self.send_response(200); self.send_header('content-type','image/svg+xml'); self.send_header('content-length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        if self.path=='/health': return self._json({'ok':True,'crm_root':str(CRM),'heartbeat_minutes':json.loads((SYSTEM/'config/heartbeat.yaml').read_text())['interval_minutes']})
        return super().do_GET()
    def do_POST(self):
        if self.path!='/action': self.send_error(404); return
        n=int(self.headers.get('content-length','0')); body=json.loads(self.rfile.read(n) or b'{}'); r=self.conductor.execute_crm_action(body['intent'],body.get('parameters',{})); self._json(r.__dict__,200 if r.ok else 400)
    def _json(self,obj,status=200):
        data=json.dumps(obj,default=str).encode(); self.send_response(status); self.send_header('content-type','application/json'); self.send_header('content-length',str(len(data))); self.end_headers(); self.wfile.write(data)
def interactive_onboarding():
    settings_path=SYSTEM/'config/settings.yaml'; settings=json.loads(settings_path.read_text())
    if settings.get('onboarding_complete') or not sys.stdin.isatty(): return
    print("This is your agent CRM. It works like a conversation, and it will learn and grow with you.")
    name=input("Your name (optional): " ).strip()
    cleanup=input("Good 30-minute daily clean-up window [07:00]: " ).strip() or '07:00'
    nightly=input("Evening improvement block [22:00-01:00]: " ).strip() or '22:00-01:00'
    try: start,end=[x.strip() for x in nightly.split('-',1)]
    except ValueError: start,end='22:00','01:00'
    settings['user_name']=name; settings['onboarding_complete']=True; settings['hours'].update({'daily_cleanup':cleanup,'nightly_development_start':start,'nightly_development_end':end}); settings_path.write_text(json.dumps(settings,indent=2)+'\n')
    Conductor(CRM).refresh_session_files(); print('Onboarding saved.')

def serve(port=8765,heartbeat=True):
    Handler.conductor=Conductor(CRM); os.chdir(SYSTEM/'ui/renderer')
    if heartbeat:
        subprocess.Popen([sys.executable,str(SYSTEM/'heartbeat.py')],cwd=str(ROOT),stdout=open(ROOT/'heartbeat.log','a'),stderr=subprocess.STDOUT)
    httpd=ThreadingHTTPServer(('127.0.0.1',port),Handler); print(f'Agent CRM running at http://127.0.0.1:{port}'); httpd.serve_forever()
def main():
    ap=argparse.ArgumentParser(description='Self-Evolving Agent CRM'); sub=ap.add_subparsers(dest='cmd')
    s=sub.add_parser('serve'); s.add_argument('--port',type=int,default=8765); s.add_argument('--no-heartbeat',action='store_true')
    a=sub.add_parser('action'); a.add_argument('intent'); a.add_argument('params',nargs='?',default='{}')
    sub.add_parser('heartbeat'); sub.add_parser('audit'); sub.add_parser('nightly'); sub.add_parser('layout')
    args=ap.parse_args(); c=Conductor(CRM)
    if args.cmd in (None,'serve'):
        interactive_onboarding(); serve(getattr(args,'port',8765),not getattr(args,'no_heartbeat',False))
    elif args.cmd=='action': print(json.dumps(c.execute_crm_action(args.intent,json.loads(args.params)).__dict__,indent=2,default=str))
    elif args.cmd=='heartbeat': os.execv(sys.executable,[sys.executable,str(SYSTEM/'heartbeat.py'),'--once'])
    elif args.cmd=='audit': print(json.dumps(c.verifier.run_full_audit(),indent=2))
    elif args.cmd=='nightly':
        sys.path.insert(0,str(SYSTEM/'orchestrator')); from orchestrator import NightlyOrchestrator; print(json.dumps(NightlyOrchestrator(CRM).run_nightly(),indent=2))
    elif args.cmd=='layout': print(json.dumps(c.render_layout(),indent=2))
if __name__=='__main__': main()
