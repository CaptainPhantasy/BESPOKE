from __future__ import annotations
from pathlib import Path
import json, re, sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from storage import CRMStore, STAGES, STAGE_DIR, Diff, StagingResult
class HiTLRequired(Exception):
    def __init__(self,message,reason): super().__init__(message); self.reason=reason

class Verifier:
    REQUIRED={'contact':['id','type','name'],'company':['id','type','name'],'deal':['id','type','name','stage'],'task':['id','type','title','status']}
    def __init__(self,root):
        self.store=CRMStore(root); self.root=Path(root)
        self.settings=json.loads((self.root/'.system/config/settings.yaml').read_text())
    def require_hitl(self,intent,p):
        if p.get('approved'): return
        if intent=='merge_contact': raise HiTLRequired('Contact merge needs confirmation','merge')
        if intent=='move_deal' and p.get('stage') in {'Won','Lost'}: raise HiTLRequired('Final deal stage needs confirmation',p.get('stage'))
        if intent in {'create_deal','update_deal','move_deal'}:
            value=p.get('value')
            if value is None and p.get('id'):
                found=self.store.find_by_id(p['id']); value=found[1].get('value',0) if found else 0
            if float(value or 0)>float(self.settings['verification'].get('high_value_threshold',25000)):
                raise HiTLRequired('High-value deal change needs confirmation','high_value')
    def pre_validate(self,live_state,diff:Diff):
        violations=[]; proposed=[]
        for ch in diff.changes:
            if ch.after is None: continue
            try: m,b=self.store.parse_record(ch.after); proposed.append((ch.relpath,m,b))
            except Exception as e: violations.append(f'{ch.relpath}: invalid record: {e}'); continue
            for k in self.REQUIRED.get(m.get('type'),[]):
                if m.get(k) in (None,''): violations.append(f"{ch.relpath}: missing {k}")
            if m.get('type')=='deal' and m.get('stage') not in STAGES: violations.append(f'{ch.relpath}: invalid stage')
            if m.get('type')=='deal' and diff.metadata.get('from_stage') and diff.metadata.get('to_stage') and diff.metadata['from_stage']!=diff.metadata['to_stage']:
                allowed=self.settings.get('pipeline',{}).get('transitions',{}).get(diff.metadata['from_stage'],[])
                if diff.metadata['to_stage'] not in allowed: violations.append(f"invalid stage transition: {diff.metadata['from_stage']} -> {diff.metadata['to_stage']}")
        # uniqueness against effective state
        if self.settings['verification'].get('duplicate_email') or self.settings['verification'].get('duplicate_phone'):
            effective={rel:m for rel,m,_ in self.store.iter_records(['Contacts'])}
            for ch in diff.changes:
                if ch.after is None: effective.pop(ch.relpath,None)
                else:
                    try:
                        m,_=self.store.parse_record(ch.after)
                        if m.get('type')=='contact': effective[ch.relpath]=m
                    except: pass
            for field,key in [('email','duplicate_email'),('phone','duplicate_phone')]:
                if not self.settings['verification'].get(key): continue
                seen={}
                for rel,m in effective.items():
                    v=(m.get(field) or '').strip().lower()
                    if v and v in seen and m.get('id')!=seen[v][0]: violations.append(f'duplicate contact {field}: {v}')
                    elif v: seen[v]=(m.get('id'),rel)
        # references in proposed data
        existing_ids={m.get('id') for _,m,_ in self.store.iter_records()}
        created_ids={m.get('id') for _,m,_ in proposed}; ids=existing_ids|created_ids
        for rel,m,_ in proposed:
            refs=[]
            for key in ['company_id','contact_id','deal_id']:
                if m.get(key): refs.append((key,m[key]))
            for key in ['contact_ids','deal_ids','task_ids']:
                refs += [(key,x) for x in m.get(key,[]) or []]
            for key,r in refs:
                if r not in ids: violations.append(f'{rel}: missing linked id {r} ({key})')
        return len(violations)==0, violations
    def post_validate(self,staged:StagingResult,preview:Diff):
        violations=[]; base=Path(staged.path)/'files'
        for ch in preview.changes:
            if ch.after is None: continue
            p=base/ch.relpath
            if not p.exists(): violations.append(f'missing staged file {ch.relpath}')
            elif p.read_text(encoding='utf-8')!=ch.after: violations.append(f'staged file differs from preview: {ch.relpath}')
        # activity can only append body text
        if preview.action=='activity.append':
            for ch in preview.changes:
                if ch.before and ch.after:
                    bm,bb=self.store.parse_record(ch.before); am,ab=self.store.parse_record(ch.after)
                    if not ab.startswith(bb.rstrip()): violations.append('activity mutation changed existing body text')
        return len(violations)==0,violations
    def run_full_audit(self):
        violations=[]; records=list(self.store.iter_records()); byid={m.get('id'):(rel,m,b) for rel,m,b in records}
        for rel,m,b in records:
            if m.get('type')=='deal':
                expected=STAGE_DIR.get(m.get('stage'))
                if expected and not rel.startswith(expected+'/'): violations.append(f'{rel}: folder/stage mismatch')
            for key in ['company_id','contact_id','deal_id']:
                if m.get(key) and m[key] not in byid: violations.append(f'{rel}: orphan {key}={m[key]}')
            for key in ['contact_ids','deal_ids','task_ids']:
                for rid in m.get(key,[]) or []:
                    if rid not in byid: violations.append(f'{rel}: orphan {key}={rid}')
        # selected inverse relationships
        for rid,(rel,m,b) in byid.items():
            if m.get('type')=='contact':
                for did in m.get('deal_ids',[]) or []:
                    d=byid.get(did)
                    if d and rid not in (d[1].get('contact_ids',[]) or []): violations.append(f'{rid}<->{did}: deal/contact inverse missing')
            if m.get('type')=='deal':
                cid=m.get('company_id')
                if cid and cid in byid and rid not in (byid[cid][1].get('deal_ids',[]) or []): violations.append(f'{rid}<->{cid}: deal/company inverse missing')
        return {'ok':not violations,'violations':violations,'record_count':len(records)}
