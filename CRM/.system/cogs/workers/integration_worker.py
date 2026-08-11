from pathlib import Path
import json, sys
sys.path.insert(0,str(Path(__file__).resolve().parent)); from base import BaseWorker
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); from storage import Diff
class IntegrationWorker(BaseWorker):
    def __init__(self,root,executor=None): super().__init__(root); self.executor=executor
    def preview(self,p): return Diff('integration.preview',[],{'params':p})
    def dry_run(self,p): return self.store.stage_diff(self.preview(p))
    def _call(self,service,action,params):
        if not self.executor: return {'status':'ready','service':service,'action':action,'params':params,'message':'Zapier executor not injected in this local process.'}
        return self.executor(service,action,params)
    def send_email(self,params): return self._call('Gmail','send_email',params)
    def create_event(self,params): return self._call('Google Calendar','create_event',params)
    def send_sms(self,params): return self._call(params.get('provider','SignalWire'),'send_sms',params)
    def invoke(self,params): return self._call(params['service'],params['action'],params.get('params',{}))
