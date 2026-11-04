"""Hand-checked teaching fixtures, not outputs of a live model."""
from copy import deepcopy


def request_payload():
    return {'request_id': 'test-001',
            'term': {'id': 'population-and-sample', 'zh': '总体与样本', 'en': 'Population and Sample',
                     'aliases': [], 'definition': '想研究的人与实际调查到的人。'},
            'question': '怎样从部分学生的记录了解研究对象？',
            'sources': [{'id': 's1', 'title': '经核对的教学说明', 'authors': [], 'year': None,
                         'doi': '', 'url': '', 'scope': 'excerpt',
                         'text': '总体是研究希望了解的目标对象集合。样本是实际获得观测的对象。研究设计决定推断范围。'}],
            'catalog': [{'id': 'variable', 'zh': '变量', 'en': 'Variable', 'aliases': [], 'kind': 'classic'}],
            'known_terms': [], 'literature_prompted': True, 'network_allowed': False}


def result_payload():
    ref = {'source_id': 's1', 'start': 0, 'end': 18}
    blocks = []
    for key, heading, text in [
        ('real_question', '你可能会问', '调查部分学生，怎样说清自己研究的是谁？'),
        ('operational_definition', '操作性定义', '总体是研究目标对象，样本是实际获得观测的对象。'),
        ('plain_explanation', '通俗解释', '想了解整锅汤的味道，先尝一勺；整锅和这一勺对应不同的范围。'),
        ('detailed_explanation', '详细解释', '先明确目标对象，再记录实际获得资料的对象。'),
        ('how_to_use', '如何使用', '在研究设计中分别写清目标人群与实际招募范围。')]:
        blocks.append({'id': key, 'heading': heading, 'paragraphs': [dict(text=text, emphasis=[],
            kind='analogy' if key == 'plain_explanation' else 'factual', refs=[deepcopy(ref)])]})
    return {'schema_version': 1, 'content_id': 'lesson-test-001', 'status': 'complete',
            'term': deepcopy(request_payload()['term']), 'blocks': blocks, 'formulas': [],
            'visual': {'kind': 'story', 'title': '整锅与一勺', 'takeaway': '区分想了解的范围和实际观察的部分。',
                'alt': '整锅汤与从中取出的一勺的教学类比。', 'origin': 'conceptual', 'refs': [],
                'payload': {'scenes': [
                    {'title': '想了解整锅', 'objects': [{'id': 'pot', 'kind': 'container', 'label': '整锅汤', 'state': 'neutral'}], 'connections': []},
                    {'title': '实际尝一勺', 'objects': [{'id': 'spoon', 'kind': 'item', 'label': '这一勺', 'state': 'selected'}], 'connections': []}]}},
            'quiz': {'question': '希望了解全校学生，实际调查一个班；这里的样本是哪部分？',
                     'options': [{'id': 'a', 'text': '实际调查的学生', 'explanation': '样本由实际获得观测的对象组成。'},
                                 {'id': 'b', 'text': '全校学生', 'explanation': '这是该研究设定的目标总体。'},
                                 {'id': 'c', 'text': '学校名称', 'explanation': '学校名称是标识信息，不是被观察对象的集合。'},
                                 {'id': 'd', 'text': '问卷中的分数', 'explanation': '分数是观测值，要与产生记录的人区分。'}], 'correct_option': 'a'},
            'relations': [{'target': 'variable', 'type': 'prerequisites', 'reason': '先理解记录的属性与取值。', 'refs': [deepcopy(ref)]}],
            'missing_evidence': [], 'provenance': {}}
