import json,zipfile
from term_explainer.online.delivery import build_delivery
from term_explainer.online.files import PrivateFiles
from tests.term_explainer.helpers import request_payload,result_payload
from .helpers import OnlineCase

class DeliveryTests(OnlineCase):
    def test_new_review_without_persistent_context_cannot_publish_package(self):
        from term_explainer.online.config import OnlineError
        request=request_payload();lesson=result_payload();lesson['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none');files=PrivateFiles(self.root/'private/tasks')
        with self.assertRaises(OnlineError):build_delivery({'id':'new-gate'},request,lesson,request['sources'],files,external_qa=False)
        self.assertFalse(files.path_for('new-gate','lesson.zip').exists())
    def test_visual_repair_rejects_changed_references_and_requires_policy(self):
        from copy import deepcopy
        from term_explainer.online.visual_repair import repair_visual
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();lesson=result_payload();v=deepcopy(lesson['visual'])
        v['refs']=[dict(source_id='s1',start=0,end=18)]
        with self.assertRaises(ValueError):repair_visual(request,lesson,request['sources'],ExternalDouble([dict(visual=v)]))
        v=deepcopy(lesson['visual'])
        with self.assertRaises(ValueError):repair_visual(request,lesson,request['sources'],ExternalDouble([dict(visual=v)]),visual_policy_version=1)

    def test_visual_only_repair_preserves_prose_quiz_and_source_positions(self):
        from copy import deepcopy
        from term_explainer.online.visual_repair import repair_visual
        from tests.term_explainer.test_feedback_visual import feedback_example
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();lesson=result_payload();before=deepcopy(lesson)
        visual=dict(kind='story',title='选择怎样改变',takeaway='观察同一人的前后变化。',alt='三轮选择及理由变化。',origin='teaching',payload=feedback_example(),refs=lesson['visual']['refs'])
        class JSONMode(ExternalDouble):
            def generate(self,messages,*args,**kwargs):
                self_outer.assertIn('JSON',messages[0]['content'])
                return super().generate(messages)
        self_outer=self
        client=JSONMode([dict(visual=visual)])
        revised=repair_visual(request,lesson,request['sources'],client)
        self.assertEqual(json.loads(client.events[0][1][1]['content'])['visual_host'],
            dict(static_visuals=True,interactive_visuals=False,model_code_allowed=False))
        self.assertEqual(lesson,before);self.assertEqual(revised['blocks'],before['blocks']);self.assertEqual(revised['quiz'],before['quiz'])
        self.assertEqual(revised['visual']['refs'],before['visual']['refs']);self.assertEqual(revised['visual']['payload']['layout'],'feedback_trace')

    def test_wording_repair_policy_is_explicit_and_keeps_legacy_wire_input(self):
        from term_explainer.online.visual_repair import repair_visual
        from term_explainer.visual_preservation import build_preservation_manifest
        from tests.term_explainer.test_pipeline import ExternalDouble
        request=request_payload();lesson=result_payload()
        clients=[ExternalDouble([dict(visual=lesson['visual'])]) for _ in range(3)]
        options=dict(issues=[dict(kind='teaching_review',reason='标明示例。',object_paths=['/title'])],
                     preservation=build_preservation_manifest(lesson['visual'],[dict(object_paths=['/title'])]))
        repair_visual(request,lesson,request['sources'],clients[0],**options)
        repair_visual(request,lesson,request['sources'],clients[1],repair_policy_version=1,**options)
        repair_visual(request,lesson,request['sources'],clients[2],repair_policy_version=2,**options)
        self.assertEqual(clients[0].events[0][1],clients[1].events[0][1])
        old=json.loads(clients[0].events[0][1][1]['content'])
        new=json.loads(clients[2].events[0][1][1]['content'])
        self.assertNotIn('repair_policy_version',old)
        self.assertEqual(new.pop('repair_policy_version'),2)
        self.assertEqual(new,old)
        self.assertIn('/title、/takeaway、/alt',clients[2].events[0][1][0]['content'])
        self.assertNotEqual(clients[0].events[0][1],clients[2].events[0][1])

    def test_long_original_can_be_archived_without_entering_selected_context(self):
        request=request_payload();lesson=result_payload();selected=request['sources'][0]
        original=dict(selected,id='original-paper',scope='full_text',text='Intro\n'+'a'*71000)
        path=self.root/'long.txt';path.write_text(original['text'],encoding='utf-8')
        files=PrivateFiles(self.root/'private/tasks')
        result=build_delivery({'id':'job-long'},request,lesson,[selected,original],files,originals={'original-paper':path},external_qa=False)
        with zipfile.ZipFile(files.path_for('job-long',result['asset_id'])) as archive:
            data=json.loads(archive.read('library.json'))
            self.assertTrue(any(s['localId']=='original-paper' and s['originalStatus']=='saved' for s in data['sources']))

    def test_real_renderer_and_exporter_create_portable_private_package(self):
        files=PrivateFiles(self.root/'private'/'tasks');request=request_payload();lesson=result_payload()
        result=build_delivery({'id':'job-test'},request,lesson,request['sources'],files,external_qa=False)
        path=files.path_for('job-test',result['asset_id']);self.assertTrue(path.is_file())
        with zipfile.ZipFile(path) as z:
            package=json.loads(z.read('library.json'));self.assertEqual(package['terms'][0]['zh'],'总体与样本')
            self.assertGreaterEqual(len(package['assets']),2)
            self.assertEqual(package['revisions'][0]['lesson']['provenance']['human_scientific_review'],'pending')
            self.assertFalse(any('response' in n or '.env' in n for n in z.namelist()))
        self.assertNotIn(str(self.root),json.dumps(result))
