from __future__ import annotations
from pathlib import Path
import importlib.util, json, sys, traceback
HERE=Path(__file__).resolve(); SYSTEM=HERE.parents[1]; COGS=SYSTEM/'cogs'; WORKERS=COGS/'workers'
sys.path[:0]=[str(COGS),str(WORKERS)]
from storage import CRMStore, ActionResult
from verifier import Verifier, HiTLRequired
from contact_worker import ContactWorker
from company_worker import CompanyWorker
from deal_worker import DealWorker
from task_worker import TaskWorker
from activity_worker import ActivityWorker
from integration_worker import IntegrationWorker

class Conductor:
    def __init__(self,root, integration_executor=None):
        self.root=Path(root).resolve(); self.store=CRMStore(self.root); self.verifier=Verifier(self.root)
        self.workers={'contact':ContactWorker(self.root),'company':CompanyWorker(self.root),'deal':DealWorker(self.root),'task':TaskWorker(self.root),'activity':ActivityWorker(self.root),'integration':IntegrationWorker(self.root,integration_executor)}
        self.intent_plans=json.loads((self.root/'.system/config/intent_plans.yaml').read_text())
        self.session_path=self.root/'.system/session/current_focus.json'; self.scratchpad={'last_intent':None,'last_entity_id':None}
    def execute_crm_action(self,intent:str,parameters:dict)->ActionResult:
        try:
            if intent not in self.intent_plans: return ActionResult(False,intent,f'Unknown CRM intent: {intent}')
            self.verifier.require_hitl(intent,parameters)
            plan=self.intent_plans[intent]
            if plan and str(plan[0]).startswith('plugin:'):
                data=self._execute_plugin(plan[0],parameters); self._audit(intent,parameters,'plugin'); self.scratchpad['last_intent']=intent; return ActionResult(True,intent,'Plugin action completed.',data,self.render_layout())
            if intent in {'send_email','create_event','send_sms'}:
                method={'send_email':'send_email','create_event':'create_event','send_sms':'send_sms'}[intent]
                data=getattr(self.workers['integration'],method)(parameters); self._audit(intent,parameters,'integration'); return ActionResult(True,intent,'Integration action prepared/executed.',data,self.render_layout())
            if intent=='activate_feature':
                from orchestrator import NightlyOrchestrator
                data=NightlyOrchestrator(self.root).activate_feature(parameters['feature_id']); self.intent_plans=json.loads((self.root/'.system/config/intent_plans.yaml').read_text()); self._audit(intent,parameters,'activated'); return ActionResult(True,intent,'Feature activated.',data,self.render_layout())
            worker=self._worker_for(intent); op=self._operation_for(intent); p={**parameters,'operation':op}
            preview=worker.preview(p)
            if not preview.changes:
                return ActionResult(True,intent,'Read completed.',preview.metadata,self.render_layout())
            ok,v=self.verifier.pre_validate(None,preview)
            if not ok: return ActionResult(False,intent,'Pre-validation failed.',violations=v)
            staged=self.store.stage_diff(preview)
            ok,v=self.verifier.post_validate(staged,preview)
            if not ok: self.store.remove_staging(staged.staging_id); return ActionResult(False,intent,'Post-validation failed.',violations=v)
            self.store.commit(staged); self.store.remove_staging(staged.staging_id)
            self._set_focus(preview.metadata.get('id')); self.scratchpad.update({'last_intent':intent,'last_entity_id':preview.metadata.get('id')}); self.refresh_session_files(); self._audit(intent,parameters,'committed')
            return ActionResult(True,intent,'Action committed.',preview.metadata,self.render_layout())
        except HiTLRequired as e:
            return ActionResult(False,intent,str(e),{'reason':e.reason},self.render_layout(),hitl_required=True)
        except Exception as e:
            self._audit(intent,parameters,'error',str(e)); return ActionResult(False,intent,f'{type(e).__name__}: {e}',violations=[traceback.format_exc(limit=2)])
    def resolve_reference(self, phrase):
        if phrase in {'that','that deal','that contact','it'} and self.scratchpad.get('last_entity_id'):
            return self.scratchpad['last_entity_id']
        try:
            focus=json.loads(self.session_path.read_text())
            return focus.get('focus_id') if phrase in {'that','that deal','that contact','it'} else None
        except Exception:
            return None
    def _execute_plugin(self,spec,params):
        _,module,func=spec.split(':',2)
        path=self.root/'.system/cogs/workers'/f'{module}.py'
        if not path.exists(): raise ValueError(f'activated plugin missing: {module}')
        mspec=importlib.util.spec_from_file_location(f'crm_plugin_{module}',path)
        mod=importlib.util.module_from_spec(mspec); mspec.loader.exec_module(mod)
        return getattr(mod,func)(self.root,params)
    def _worker_for(self,intent):
        return self.workers[{'create_contact':'contact','update_contact':'contact','merge_contact':'contact','list_contacts':'contact','create_company':'company','update_company':'company','create_deal':'deal','update_deal':'deal','move_deal':'deal','create_task':'task','complete_task':'task','list_overdue_tasks':'task','append_activity':'activity'}[intent]]
    def _operation_for(self,intent):
        return {'create_contact':'create','update_contact':'update','merge_contact':'merge','list_contacts':'list','create_company':'create','update_company':'update','create_deal':'create','update_deal':'update','move_deal':'move','create_task':'create','complete_task':'complete','list_overdue_tasks':'list_overdue','append_activity':'append'}[intent]
    def _set_focus(self,rid):
        if not rid:return
        found=self.store.find_by_id(rid)
        if found:
            self.session_path.write_text(json.dumps({'focus_type':found[1].get('type'),'focus_id':rid},indent=2))
    def _audit(self,intent,params,status,error=None):
        safe={k:('***' if any(x in k.lower() for x in ['token','password','secret']) else v) for k,v in params.items()}
        entry={'at':self.store.now(),'intent':intent,'status':status,'parameters':safe}
        if error: entry['error']=error
        with (self.root/'.system/audit.log').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    def refresh_session_files(self):
        deals=[]; counts={s:{'count':0,'value':0.0} for s in ['New','Qualified','Proposal','Negotiation','Won','Lost']}
        for rel,m,b in self.store.iter_records(['Deals']):
            s=m.get('stage','New'); counts.setdefault(s,{'count':0,'value':0}); counts[s]['count']+=1; counts[s]['value']+=float(m.get('value',0) or 0); deals.append(m)
        lines=['# Pipeline Snapshot','','| Stage | Deals | Value |','|---|---:|---:|']+[f"| {s} | {v['count']} | ${v['value']:,.2f} |" for s,v in counts.items()]
        (self.root/'.system/session/pipeline_snapshot.md').write_text('\n'.join(lines)+'\n')
        overdue=self.workers['task'].preview({'operation':'list_overdue'}).metadata['records']
        brief=['# Daily Brief','',f"Open pipeline: {sum(v['count'] for k,v in counts.items() if k not in {'Won','Lost'})} deals.",f"Overdue tasks: {len(overdue)}."]
        (self.root/'.system/session/daily_brief.md').write_text('\n'.join(brief)+'\n')
    def render_layout(self):
        try: focus=json.loads(self.session_path.read_text())
        except: focus={'focus_type':'daily_review','focus_id':None}
        entity=None
        if focus.get('focus_id'):
            found=self.store.find_by_id(focus['focus_id']); entity=found[1] if found else None
        ftype=focus.get('focus_type','daily_review'); image={'deal':'card-deal','contact':'card-contact'}.get(ftype,'card-agenda')
        overdue=self.workers['task'].preview({'operation':'list_overdue'}).metadata['records']
        return {'focus':ftype,'top_left':{'image':image,'data':entity or {'title':'Daily Review'}},'top_right':{'image':'actions-list','data':{'actions':['Add contact','Add deal','Add task','Review pipeline']}},'bottom_left':{'image':'timeline-feed','data':{'items':self._recent_audit(8)}},'bottom_right':{'image':'pipeline-mini','data':{'overdue_tasks':len(overdue),'related':self._related(entity)}}}
    def _recent_audit(self,n):
        p=self.root/'.system/audit.log'
        if not p.exists(): return []
        lines=p.read_text().splitlines()[-n:]; out=[]
        for x in lines:
            try: out.append(json.loads(x))
            except: pass
        return out
    def _related(self,entity):
        if not entity:return []
        ids=[]
        for k in ['company_id','contact_id','deal_id']:
            if entity.get(k): ids.append(entity[k])
        for k in ['contact_ids','deal_ids','task_ids']: ids.extend(entity.get(k,[]) or [])
        return ids[:10]
