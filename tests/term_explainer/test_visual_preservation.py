from copy import deepcopy
import unittest
from term_explainer.visual_preservation import build_preservation_manifest,validate_preserved_visual


def three_scene_visual():
    return dict(kind='story',origin='teaching',title='固定名额下的加码扩散',
        takeaway='同一名额下，乙先加时甲跟随，名次未变而投入增加。',
        alt='三幅教学故事图',refs=[dict(source_id='s1',start=0,end=18)],
        presentation=dict(version=1,focus='process',numeric_role='relative',layout='story',interaction='none'),
        payload=dict(layout='scenes',ordered=True,scenes=[
            dict(title='起点',objects=[
                dict(id='a',label='甲 6小时',kind='person',state='neutral'),
                dict(id='b',label='乙 6小时',kind='person',state='neutral')],
                connections=[]),
            dict(title='乙先加码',objects=[
                dict(id='a',label='甲 6小时',kind='person',state='neutral'),
                dict(id='b',label='乙 8小时',kind='person',state='selected')],
                connections=[{'from':'b','to':'a','label':'暂时领先','relation':'comparison'}]),
            dict(title='甲跟随',objects=[
                dict(id='a',label='甲 8小时',kind='person',state='neutral'),
                dict(id='b',label='乙 8小时',kind='person',state='neutral')],
                connections=[{'from':'b','to':'a','label':'名次未变','relation':'association'}])]))


def issue(paths):
    return dict(kind='teaching_review',reason='r',object_paths=paths,visual_fingerprint='x')


class PreservationTests(unittest.TestCase):
    def test_manifest_and_pass_when_content_preserved_with_added_scene(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes'])])
        candidate=deepcopy(visual)
        candidate['payload']['scenes'].insert(1,dict(title='乙暂时领先',objects=[
            dict(id='a',label='甲 6小时',kind='person',state='neutral'),
            dict(id='b',label='乙 8小时',kind='person',state='selected')],connections=[]))
        validate_preserved_visual(candidate,manifest)

    def test_scene_removal_is_rejected_even_when_review_paths_are_coarse(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes'])])
        candidate=deepcopy(visual);candidate['payload']['scenes']=candidate['payload']['scenes'][:2]
        with self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)

    def test_object_removal_and_unauthorized_value_change_are_rejected(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes/1/objects/0'])])
        dropped=deepcopy(visual);dropped['payload']['scenes'][1]['objects']=[dropped['payload']['scenes'][1]['objects'][1]]
        with self.assertRaises(ValueError):validate_preserved_visual(dropped,manifest)
        changed=deepcopy(visual);changed['payload']['scenes'][2]['objects'][1]['label']='乙 6小时'
        with self.assertRaises(ValueError):validate_preserved_visual(changed,manifest)

    def test_authorized_object_rewording_is_allowed(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes/2/objects/1','/payload/scenes/2/connections/0'])])
        candidate=deepcopy(visual)
        candidate['payload']['scenes'][2]['objects'][1]['state']='selected'
        candidate['payload']['scenes'][2]['connections'][0]['label']='相对同一名额未变'
        validate_preserved_visual(candidate,manifest)

    def test_identity_fields_survive_authorized_edit(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes/0/objects/0'])])
        candidate=deepcopy(visual);candidate['payload']['scenes'][0]['objects'][0]['kind']='container'
        with self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)

    def test_refs_presentation_title_and_takeaway_are_immutable(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes'])])
        for mutate in (lambda c:c['refs'].__setitem__(0,dict(source_id='s1',start=0,end=9)),
                       lambda c:c['presentation'].__setitem__('layout','chart'),
                       lambda c:c.__setitem__('title','另一个标题'),
                       lambda c:c.__setitem__('takeaway','另一个结论')):
            candidate=deepcopy(visual);mutate(candidate)
            with self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)

    def test_exact_review_paths_authorize_only_the_named_wording_fields(self):
        visual=three_scene_visual()
        for field in ('title','takeaway','alt'):
            with self.subTest(field=field):
                manifest=build_preservation_manifest(visual,[issue(['/'+field])])
                candidate=deepcopy(visual)
                candidate[field]='教学示例：'+candidate[field]
                validate_preserved_visual(candidate,manifest)
                other='takeaway' if field=='title' else 'title'
                candidate[other]='未经授权的另一处改写'
                with self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)

    def test_wording_authorization_does_not_allow_data_or_provenance_changes(self):
        visual=three_scene_visual()
        manifest=build_preservation_manifest(visual,[issue(['/title','/takeaway','/alt'])])
        for field in ('kind','origin','refs','presentation','payload'):
            candidate=deepcopy(visual)
            candidate['title']='教学示例：'+candidate['title']
            if field=='payload':candidate[field]['scenes'][1]['objects'][1]['label']='乙 80小时'
            elif field=='refs':candidate[field][0]['end']=9
            elif field=='presentation':candidate[field]['numeric_role']='none'
            else:candidate[field]='changed'
            with self.subTest(field=field),self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)

    def test_coarse_or_child_paths_do_not_authorize_title_change(self):
        visual=three_scene_visual()
        for paths in ([],['/'],['/title/anything'],['/payload/scenes']):
            candidate=deepcopy(visual);candidate['title']='未授权改写'
            with self.subTest(paths=paths),self.assertRaises(ValueError):
                validate_preserved_visual(candidate,build_preservation_manifest(visual,[issue(paths)]))

    def test_single_scene_term_keeps_working_without_forced_story_expansion(self):
        visual=three_scene_visual();visual['payload']['scenes']=visual['payload']['scenes'][:1]
        visual['takeaway']='单场景即可说明。'
        manifest=build_preservation_manifest(visual,[issue(['/payload/scenes/0/objects/0'])])
        candidate=deepcopy(visual)
        validate_preserved_visual(candidate,manifest)

    def test_statistical_series_and_axes_are_immutable_without_authorization(self):
        visual=dict(kind='statistical',origin='source',title='分布对比',takeaway='两组分布',alt='直方图',
            refs=[dict(source_id='s1',start=0,end=5)],
            data_semantics=dict(type='independent',denominator=None,rounding_digits=1),
            presentation=dict(version=1,focus='distribution',numeric_role='measure',layout='chart',interaction='none'),
            payload=dict(chart_type='histogram',x_label='得分',y_label='人数',x_unit='分',y_unit='人',
                series=[dict(label='实验组',bin_edges=[0,10,20],counts=[5,8])] if True else []))
        visual['payload']['series']=[dict(label='实验组',bin_edges=[0,10,20],counts=[5,8]),
                                     dict(label='对照组',bin_edges=[0,10,20],counts=[6,7])]
        manifest=build_preservation_manifest(visual,[issue([])])
        candidate=deepcopy(visual);candidate['payload']['series'][1]['counts']=[9,9]
        with self.assertRaises(ValueError):validate_preserved_visual(candidate,manifest)
        validate_preserved_visual(deepcopy(visual),manifest)
