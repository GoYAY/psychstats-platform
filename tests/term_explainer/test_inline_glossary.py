from copy import deepcopy
from html.parser import HTMLParser
import json
import unittest
from unittest.mock import patch
from .helpers import request_payload,result_payload
from term_explainer.contract import validate_request,validate_result
from term_explainer.reader import render_lesson


class Markup(HTMLParser):
    def __init__(self,text):
        super().__init__(); self.triggers=[]; self.current=None; self.scripts=[]; self.in_script=False
        self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'term-help' in a.get('class','').split():
            if self.current: raise AssertionError('nested terminology controls')
            self.current=dict(tag=tag,attrs=a,text=''); self.triggers.append(self.current)
        if tag=='script': self.in_script=True
    def handle_endtag(self,tag):
        if self.current and tag==self.current['tag']: self.current=None
        if tag=='script': self.in_script=False
    def handle_data(self,data):
        if self.current: self.current['text']+=data
        if self.in_script: self.scripts.append(data)


class InlineGlossaryTests(unittest.TestCase):
    def entry(self,term='TIRT',**changes):
        return dict(dict(id='tirt',term=term,aliases=[],explanation='用陈述之间的选择共同估计多种特质。',
            refs=[dict(source_id='s1',start=0,end=18)],target=None),**changes)
    def page(self,entries,text,catalog=None):
        data=result_payload(); data['glossary']=entries
        data['blocks'][2]['paragraphs'][0].update(text=text,emphasis=[])
        request=validate_request(request_payload())
        return render_lesson(validate_result(data,request),catalog=catalog or request.catalog)
    def test_source_bound_explanations_are_rendered_as_local_controls(self):
        page=self.page([self.entry()],'先了解TIRT。')
        control=next(t for t in Markup(page).triggers if t['text']=='TIRT')
        self.assertEqual(control['tag'],'button')
        self.assertNotIn('href',control['attrs'])
        self.assertIn('用陈述之间的选择共同估计多种特质。',page)
    def test_catalogue_matches_alone_do_not_create_help_controls(self):
        page=self.page([],'变量、标准误和模型估计。')
        self.assertEqual(Markup(page).triggers,[])
    def test_unknown_evidence_and_executable_extra_fields_are_rejected(self):
        for change in [dict(refs=[]),dict(refs=[dict(source_id='unknown',start=0,end=1)]),dict(html='<script>bad</script>')]:
            data=result_payload(); data['glossary']=[self.entry(**change)]
            with self.subTest(change=change),self.assertRaises(ValueError):validate_result(data,validate_request(request_payload()))
    def test_aliases_and_complete_variants_win_over_shorter_names(self):
        entries=[self.entry(),self.entry('IRT',id='irt'),self.entry('DTP（via DSM）',id='via-dsm',aliases=['DTP (via DSM)']),self.entry('DSM',id='dsm')]
        page=self.page(entries,'TIRT、IRT、DTP（via DSM）、DTP (via DSM)、DSM。')
        terms=[t['text'] for t in Markup(page).triggers]
        self.assertEqual(terms,['TIRT','IRT','DTP（via DSM）','DTP (via DSM)','DSM'])
    def test_current_complete_term_is_not_split_into_another_term(self):
        data=result_payload(); req=request_payload()
        req['term'].update(id='latent-variable',zh='潜变量',en='Latent Variable')
        data['term']=deepcopy(req['term']); data['glossary']=[self.entry('变量',id='variable-note')]
        data['blocks'][2]['paragraphs'][0].update(text='潜变量与变量需要区分。',emphasis=[])
        page=render_lesson(validate_result(data,validate_request(req)),catalog=req['catalog'])
        self.assertEqual([t['text'] for t in Markup(page).triggers],['变量'])
    def test_classic_link_is_added_only_after_matching_catalogue_entry_exists(self):
        note=self.entry('区分度',id='discrimination')
        before=Markup(self.page([note],'区分度。')).triggers[0]
        self.assertEqual(before['tag'],'button')
        catalogue=[dict(id='item-discrimination',zh='项目区分度',aliases=['区分度'],kind='classic')]
        # A claimed catalogue kind alone must never establish route availability.
        unpublished=Markup(self.page([note],'区分度。',catalogue)).triggers[0]
        self.assertEqual(unpublished['tag'],'button')
        with patch('term_explainer.inline_glossary.classic_catalogue',return_value=catalogue):
            after=Markup(self.page([note],'区分度。',catalogue)).triggers[0]
        self.assertEqual(after['tag'],'button')
        self.assertNotIn('href',after['attrs'])
        with patch('term_explainer.inline_glossary.classic_catalogue',return_value=catalogue):
            page=self.page([note],'区分度。',catalogue)
        notes=next(json.loads(s) for s in Markup(page).scripts if 'discrimination' in s)
        self.assertEqual(notes['discrimination']['href'],'https://cdst.site/psy-stats/terms/item-discrimination.html')
        pending=Markup(self.page([note],'区分度。',[dict(catalogue[0],kind='pending')])).triggers[0]
        self.assertEqual(pending['tag'],'button')
    def test_unverified_classic_route_is_absent_from_prose_and_related_links(self):
        catalogue=[dict(id='page-that-does-not-exist',zh='不存在的术语',kind='classic')]
        data=result_payload(); request=validate_request(request_payload())
        data['blocks'][2]['paragraphs'][0].update(text='不存在的术语。',emphasis=[])
        data['relations']=[dict(target='page-that-does-not-exist',kind='related',reason='用于理解主术语。')]
        # Rendered input can also come from stored jobs; it must recheck live routes.
        page=render_lesson(data,catalog=catalogue)
        self.assertNotIn('/terms/page-that-does-not-exist.html',page)
        self.assertIn('待补充',page)
    def test_ambiguous_alias_does_not_create_a_guessed_link(self):
        entries=[dict(id='one',zh='词一',aliases=['区分度'],kind='classic'),dict(id='two',zh='词二',aliases=['区分度'],kind='classic')]
        trigger=Markup(self.page([self.entry('区分度')],'区分度。',entries)).triggers[0]
        self.assertEqual(trigger['tag'],'button')
    def test_unavailable_complete_term_still_protects_its_shorter_component(self):
        catalogue=[dict(id='variable',zh='变量',kind='classic'),dict(id='nonexistent-latent-variable',zh='潜变量',kind='classic')]
        page=self.page([self.entry('变量',id='variable-note')],'潜变量与变量。',catalogue)
        self.assertEqual([t['text'] for t in Markup(page).triggers],['变量'])
    def test_english_short_name_is_not_extracted_from_other_words(self):
        page=self.page([self.entry(),self.entry('IRT',id='irt')],'DIRT TIRT IRT IRTests。')
        self.assertEqual([t['text'] for t in Markup(page).triggers],['TIRT','IRT'])
    def test_unicode_lookalikes_are_not_mistaken_for_ascii_method_aliases(self):
        page=self.page([self.entry('IRT',id='irt'),self.entry('SEM',id='sem')],'İRT ırt ſEM IRT irt SEM。')
        self.assertEqual([t['text'] for t in Markup(page).triggers],['IRT','irt','SEM'])
    def test_browser_note_data_never_contains_evidence_refs_or_raw_sources(self):
        page=self.page([self.entry()],'TIRT。')
        parser=Markup(page)
        notes=next(json.loads(s) for s in parser.scripts if '用陈述之间' in s)
        self.assertEqual(set(notes['tirt']),{'title','explanation','href'})
    def test_prose_and_explanation_are_not_executed_as_html(self):
        page=self.page([self.entry(explanation='解释包含 </script><img src=x onerror=alert(1)>。')],'<script>bad()</script>TIRT。')
        self.assertNotIn('<script>bad()',page)
        self.assertNotIn('<img src=x',page)
        self.assertIn('&lt;script&gt;',page)
    def test_sources_show_only_one_title_and_never_embed_raw_passages(self):
        request=validate_request(request_payload()); data=result_payload()
        sources=deepcopy(request.sources); sources[0].update(title='同一篇文献',text='PRIVATE_EXCERPT_MUST_NOT_REACH_HTML',authors=['PRIVATE_AUTHOR'],year=2025,doi='10.1234/test')
        sources.append(dict(sources[0],id='s1-appendix'))
        original=deepcopy(sources)
        page=render_lesson(validate_result(data,request),sources=sources)
        self.assertEqual(page.count('同一篇文献'),1)
        for private in ['PRIVATE_EXCERPT','PRIVATE_AUTHOR','<blockquote','引用片段']:
            self.assertNotIn(private,page)
        self.assertEqual(sources,original)
    def test_source_title_deduplicates_even_if_one_slice_has_no_doi(self):
        data=result_payload()
        sources=[dict(title='同一篇 文献',doi='10.1234/test'),dict(title='同一篇文献',doi='')]
        page=render_lesson(data,sources=sources)
        self.assertEqual(page.count('<li>同一篇'),1)
    def test_help_controls_are_confined_to_four_teaching_body_blocks(self):
        data=result_payload(); data['glossary']=[self.entry()]
        for b in data['blocks']: b['paragraphs'][0].update(text='TIRT。',emphasis=[])
        data['blocks'].append(dict(id='academic_expression',heading='学术表达',paragraphs=[dict(text='TIRT。',emphasis=[],kind='illustration',refs=[])]))
        data['limitations']=[dict(text='TIRT。',refs=[dict(source_id='s1',start=0,end=18)])]
        data['formulas']=[dict(latex='x',symbols=[dict(symbol='x',meaning='TIRT。')],refs=[dict(source_id='s1',start=0,end=18)])]
        data['quiz']['question']='TIRT？'
        data['visual']['takeaway']='TIRT。'
        from types import SimpleNamespace
        page=render_lesson(validate_result(data,validate_request(request_payload())),
            SimpleNamespace(desktop='one.svg',mobile='two.svg',alt='教学示意'))
        self.assertEqual(len(Markup(page).triggers),4)
        for identity in ('real_question','academic_expression','evidence-scope','formulas','quiz'):
            content=page.split('id="'+identity+'"',1)[1].split('</section>',1)[0]
            self.assertNotIn('class="term-help',content,identity)
        self.assertNotIn('class="term-help',page.split('<figcaption>',1)[1].split('</figcaption>',1)[0])
    def test_unrelated_main_term_uses_the_same_explicit_helper_selection(self):
        req=request_payload(); data=result_payload()
        req['term'].update(id='measurement-invariance',zh='测量不变性',en='Measurement Invariance')
        data['term']=deepcopy(req['term'])
        data['glossary']=[self.entry('载荷不变性',id='metric',aliases=['metric invariance'])]
        data['blocks'][3]['paragraphs'][0].update(text='测量不变性包括载荷不变性。按题组整理，再交给模型估计；变量用于记录。',emphasis=[])
        page=render_lesson(validate_result(data,validate_request(req)),catalog=req['catalog'])
        self.assertEqual([t['text'] for t in Markup(page).triggers],['载荷不变性'])
