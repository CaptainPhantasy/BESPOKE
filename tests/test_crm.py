from pathlib import Path
import json, shutil, sys, tempfile, unittest
PROJECT=Path(__file__).resolve().parents[1]; BASE=PROJECT/'CRM'; SYSTEM=BASE/'.system'; sys.path.insert(0,str(SYSTEM)); sys.path.insert(0,str(SYSTEM/'orchestrator')); sys.path.insert(0,str(SYSTEM/'cogs'))
from conductor import Conductor
from orchestrator import NightlyOrchestrator
from heartbeat import Heartbeat
class CRMTests(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp())/'CRM'; shutil.copytree(BASE,self.tmp); self.c=Conductor(self.tmp)
    def tearDown(self): shutil.rmtree(self.tmp.parent,ignore_errors=True)
    def test_create_contact_commit(self):
        r=self.c.execute_crm_action('create_contact',{'name':'Jamie Lee','email':'jamie@example.com'}); self.assertTrue(r.ok,r); self.assertIsNotNone(self.c.store.find_by_id(r.data['id']))
    def test_duplicate_email_rejected(self):
        r=self.c.execute_crm_action('create_contact',{'name':'Duplicate','email':'alex@example.com'}); self.assertFalse(r.ok); self.assertTrue(any('duplicate' in x for x in r.violations))
    def test_move_deal_changes_folder(self):
        r=self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Qualified'}); self.assertTrue(r.ok); self.assertTrue((self.tmp/'Deals/Stage-Qualified/deal-demo.md').exists()); self.assertFalse((self.tmp/'Deals/Stage-New/deal-demo.md').exists())
    def test_hitl_for_won(self):
        self.assertTrue(self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Qualified'}).ok); self.assertTrue(self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Proposal'}).ok); r=self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Won'}); self.assertTrue(r.hitl_required); r2=self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Won','approved':True}); self.assertTrue(r2.ok)
    def test_activity_append(self):
        before=(self.tmp/'Contacts/contact-demo.md').read_text(); r=self.c.execute_crm_action('append_activity',{'id':'contact-demo','text':'Called customer'}); self.assertTrue(r.ok); after=(self.tmp/'Contacts/contact-demo.md').read_text(); self.assertIn('Called customer',after); self.assertGreater(len(after),len(before))
    def test_audit_seed_clean(self): self.assertTrue(self.c.verifier.run_full_audit()['ok'],self.c.verifier.run_full_audit())
    def test_heartbeat_five_minutes(self): self.assertEqual(json.loads((self.tmp/'.system/config/heartbeat.yaml').read_text())['interval_minutes'],5); self.assertIn('actions',Heartbeat(self.tmp).tick())
    def test_invalid_stage_transition_rejected(self):
        r=self.c.execute_crm_action('move_deal',{'id':'deal-demo','stage':'Negotiation'})
        self.assertFalse(r.ok); self.assertTrue(any('transition' in x for x in r.violations))
    def test_inverse_links_on_new_deal(self):
        r=self.c.execute_crm_action('create_deal',{'name':'Second Deal','stage':'New','value':1000,'contact_ids':['contact-demo'],'company_id':'company-demo'})
        self.assertTrue(r.ok,r); did=r.data['id']
        c=self.c.store.find_by_id('contact-demo')[1]; co=self.c.store.find_by_id('company-demo')[1]
        self.assertIn(did,c.get('deal_ids',[])); self.assertIn(did,co.get('deal_ids',[]))
    def test_stored_high_value_requires_hitl(self):
        r=self.c.execute_crm_action('create_deal',{'name':'Large','stage':'New','value':30000,'approved':True}); self.assertTrue(r.ok)
        r2=self.c.execute_crm_action('update_deal',{'id':r.data['id'],'name':'Large revised'}); self.assertTrue(r2.hitl_required)
    def test_nightly_feature_activates_and_runs(self):
        n=NightlyOrchestrator(self.tmp); proposal=n.run_nightly(); self.assertTrue(proposal['ok'])
        a=self.c.execute_crm_action('activate_feature',{'feature_id':proposal['feature_id']}); self.assertTrue(a.ok,a)
        r=self.c.execute_crm_action('pipeline_report',{}); self.assertTrue(r.ok,r); self.assertTrue((self.tmp/r.data['report']).exists())
    def test_layout_under_200ms(self):
        import time
        start=time.perf_counter(); self.c.render_layout(); elapsed=time.perf_counter()-start; self.assertLess(elapsed,0.2)
    def test_daily_cleanup_archives_old_completed_task(self):
        r=self.c.execute_crm_action('create_task',{'title':'Old completed','due':'2026-01-01'}); self.assertTrue(r.ok)
        tid=r.data['id']; self.assertTrue(self.c.execute_crm_action('complete_task',{'id':tid}).ok)
        rel,meta,body=self.c.store.find_by_id(tid); meta['completed_at']='2026-01-02T12:00:00-05:00'; (self.tmp/rel).write_text(self.c.store.dump_record(meta,body))
        Heartbeat(self.tmp).daily_cleanup(); self.assertTrue((self.tmp/'Tasks/Archive'/f'{tid}.md').exists())
    def test_nightly_three_roles(self):
        r=NightlyOrchestrator(self.tmp).run_nightly(); self.assertTrue(r['ok']); self.assertTrue((self.tmp/'.system/orchestrator/proposals'/r['feature_id']/'manifest.json').exists())
if __name__=='__main__': unittest.main()
