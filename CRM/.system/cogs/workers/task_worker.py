from pathlib import Path
from datetime import date
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff, FileChange
class TaskWorker(BaseWorker):
    def preview(self,p):
        op=p.get('operation','create')
        if op=='list_overdue':
            rows=[]
            for rel,m,b in self.store.iter_records(['Tasks']):
                if m.get('status')!='completed' and m.get('due') and m['due'] < date.today().isoformat(): rows.append(m)
            return Diff('task.list_overdue',[],{'records':rows})
        rid=p.get('id') or self.store.new_id('task'); found=self.store.find_by_id(rid)
        old,body=(found[1],found[2]) if found else ({},f"# {p.get('title','Task')}\n")
        old_deal=old.get('deal_id'); meta={**old,**{k:v for k,v in p.items() if k not in {'operation','body','approved'}}}; meta.update({'id':rid,'type':'task','updated_at':self.store.now()}); meta.setdefault('created_at',self.store.now()); meta.setdefault('status','open')
        if op=='complete': meta['status']='completed'; meta['completed_at']=self.store.now()
        rel=found[0] if found else f'Tasks/{rid}.md'; changes=[FileChange(rel,self.store.read_text(rel),self.store.dump_record(meta,p.get('body',body)))]
        new_deal=meta.get('deal_id')
        if old_deal!=new_deal:
            if old_deal:self._deal_link(changes,old_deal,rid,False)
            if new_deal:self._deal_link(changes,new_deal,rid,True)
        elif new_deal and not found:self._deal_link(changes,new_deal,rid,True)
        return Diff(f'task.{op}',changes,{'id':rid})
    def _deal_link(self,changes,did,rid,add):
        d=self.store.find_by_id(did)
        if not d:return
        rel,m,b=d; ids=list(m.get('task_ids',[]) or []); m['task_ids']=sorted(set(ids+[rid])) if add else [x for x in ids if x!=rid]; m['updated_at']=self.store.now(); changes.append(FileChange(rel,self.store.read_text(rel),self.store.dump_record(m,b)))
