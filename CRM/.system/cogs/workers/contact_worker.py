from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff, FileChange
class ContactWorker(BaseWorker):
    def preview(self, params):
        op=params.get('operation','create')
        if op=='list': return Diff('contact.list',[],{'records':[m for _,m,_ in self.store.iter_records(['Contacts'])]})
        if op=='merge': return self._merge(params)
        rid=params.get('id') or self.store.new_id('contact'); found=self.store.find_by_id(rid)
        old_meta, body=(found[1],found[2]) if found else ({}, f"# {params.get('name','Contact')}\n\n## Activity\n")
        old_company=old_meta.get('company_id')
        meta={**old_meta, **{k:v for k,v in params.items() if k not in {'operation','body','approved'}}}
        meta.update({'id':rid,'type':'contact','updated_at':self.store.now()}); meta.setdefault('created_at',self.store.now()); meta.setdefault('deal_ids',[])
        rel=found[0] if found else f'Contacts/{rid}.md'; changes=[FileChange(rel,self.store.read_text(rel),self.store.dump_record(meta,params.get('body',body)))]
        new_company=meta.get('company_id')
        if old_company != new_company:
            if old_company: self._company_link(changes,old_company,rid,False)
            if new_company: self._company_link(changes,new_company,rid,True)
        elif new_company and not found: self._company_link(changes,new_company,rid,True)
        return Diff(f'contact.{op}',changes,{'id':rid})
    def _company_link(self,changes,cid,rid,add):
        c=self.store.find_by_id(cid)
        if not c: return
        rel,m,b=c; ids=list(m.get('contact_ids',[]) or [])
        ids=sorted(set(ids+[rid])) if add else [x for x in ids if x!=rid]
        m['contact_ids']=ids; m['updated_at']=self.store.now(); changes.append(FileChange(rel,self.store.read_text(rel),self.store.dump_record(m,b)))
    def _merge(self,p):
        keep=self.store.find_by_id(p['keep_id']); drop=self.store.find_by_id(p['merge_id'])
        if not keep or not drop: raise ValueError('contact to merge not found')
        km,kb=keep[1],keep[2]; dm=drop[1]
        for key in ['email','phone','company_id']:
            if not km.get(key) and dm.get(key): km[key]=dm[key]
        km['deal_ids']=sorted(set(km.get('deal_ids',[])+dm.get('deal_ids',[]))); km['updated_at']=self.store.now()
        changes=[FileChange(keep[0],self.store.read_text(keep[0]),self.store.dump_record(km,kb)), FileChange(drop[0],self.store.read_text(drop[0]),None,'delete')]
        for rel,m,b in self.store.iter_records(['Deals','Companies']):
            changed=False
            for key in ['contact_ids']:
                ids=m.get(key,[]) or []
                if p['merge_id'] in ids:
                    m[key]=sorted(set([p['keep_id'] if x==p['merge_id'] else x for x in ids])); changed=True
            if changed:
                m['updated_at']=self.store.now(); changes.append(FileChange(rel,self.store.read_text(rel),self.store.dump_record(m,b)))
        return Diff('contact.merge',changes,{'keep_id':p['keep_id'],'merge_id':p['merge_id'],'id':p['keep_id']})
