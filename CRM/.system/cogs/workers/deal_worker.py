from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff, FileChange, STAGES, STAGE_DIR
class DealWorker(BaseWorker):
    def preview(self,p):
        op=p.get('operation','create'); rid=p.get('id') or self.store.new_id('deal'); found=self.store.find_by_id(rid)
        old,body=(found[1],found[2]) if found else ({},f"# {p.get('name','Deal')}\n\n## Activity\n")
        stage=p.get('stage',old.get('stage','New'))
        if stage not in STAGES: raise ValueError(f'invalid stage: {stage}')
        old_contacts=set(old.get('contact_ids',[]) or []); old_company=old.get('company_id')
        meta={**old,**{k:v for k,v in p.items() if k not in {'operation','body','approved'}}}; meta.update({'id':rid,'type':'deal','stage':stage,'updated_at':self.store.now()}); meta.setdefault('created_at',self.store.now()); meta.setdefault('contact_ids',[]); meta.setdefault('task_ids',[]); meta.setdefault('value',0)
        newrel=f"{STAGE_DIR[stage]}/{rid}.md"; changes=[]
        if found and found[0]!=newrel: changes.append(FileChange(found[0],self.store.read_text(found[0]),None,'delete'))
        changes.append(FileChange(newrel,self.store.read_text(newrel),self.store.dump_record(meta,p.get('body',body))))
        new_contacts=set(meta.get('contact_ids',[]) or []); new_company=meta.get('company_id')
        for cid in old_contacts-new_contacts: self._link(changes,cid,'deal_ids',rid,False)
        for cid in new_contacts-old_contacts: self._link(changes,cid,'deal_ids',rid,True)
        if not found:
            for cid in new_contacts: self._link(changes,cid,'deal_ids',rid,True)
        if old_company != new_company:
            if old_company:self._link(changes,old_company,'deal_ids',rid,False)
            if new_company:self._link(changes,new_company,'deal_ids',rid,True)
        elif new_company and not found:self._link(changes,new_company,'deal_ids',rid,True)
        return Diff(f'deal.{op}',changes,{'id':rid,'from_stage':old.get('stage'),'to_stage':stage})
    def _link(self,changes,target_id,key,rid,add):
        target=self.store.find_by_id(target_id)
        if not target:return
        rel,m,b=target; ids=list(m.get(key,[]) or []); ids=sorted(set(ids+[rid])) if add else [x for x in ids if x!=rid]; m[key]=ids; m['updated_at']=self.store.now()
        before=self.store.read_text(rel); after=self.store.dump_record(m,b)
        for i,ch in enumerate(changes):
            if ch.relpath==rel and ch.after is not None:
                try:
                    mm,bb=self.store.parse_record(ch.after); current=list(mm.get(key,[]) or []); mm[key]=sorted(set(current+[rid])) if add else [x for x in current if x!=rid]; mm['updated_at']=self.store.now(); changes[i]=FileChange(rel,ch.before,self.store.dump_record(mm,bb)); return
                except: pass
        changes.append(FileChange(rel,before,after))
