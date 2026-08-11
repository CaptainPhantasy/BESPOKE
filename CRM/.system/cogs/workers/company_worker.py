from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff, FileChange
class CompanyWorker(BaseWorker):
    def preview(self,p):
        op=p.get('operation','create'); rid=p.get('id') or self.store.new_id('company'); found=self.store.find_by_id(rid)
        old,body=(found[1],found[2]) if found else ({},f"# {p.get('name','Company')}\n\n## Activity\n")
        meta={**old,**{k:v for k,v in p.items() if k not in {'operation','body','approved'}}}; meta.update({'id':rid,'type':'company','updated_at':self.store.now()}); meta.setdefault('created_at',self.store.now()); meta.setdefault('contact_ids',[]); meta.setdefault('deal_ids',[])
        rel=found[0] if found else f'Companies/{rid}.md'; return Diff(f'company.{op}',[FileChange(rel,self.store.read_text(rel),self.store.dump_record(meta,p.get('body',body)))],{'id':rid})
