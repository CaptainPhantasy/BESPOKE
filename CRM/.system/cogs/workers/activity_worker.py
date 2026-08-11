from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff, FileChange
class ActivityWorker(BaseWorker):
    def preview(self,p):
        found=self.store.find_by_id(p['id'])
        if not found: raise ValueError('entity not found')
        rel,m,body=found; stamp=self.store.now(); line=f"- {stamp}: {p['text'].strip()}\n"
        if '## Activity' not in body: body=body.rstrip()+"\n\n## Activity\n"
        after_body=body.rstrip()+"\n"+line; m['updated_at']=stamp
        return Diff('activity.append',[FileChange(rel,self.store.read_text(rel),self.store.dump_record(m,after_body))],{'id':p['id'],'appended':line})
