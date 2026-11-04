"""Host-side preservation contract for model-repaired diagrams.

The manifest is built by the host from the current visual plus the bound
issues; the repaired candidate must keep baseline semantic content unless a
review path explicitly authorizes a targeted change.  Model assertions never
relax this check, and removal of baseline scenes/objects/connections is never
authorized — repairs may adjust wording/state of authorized targets, add
scenes or add objects, but not delete teaching content.
"""
from copy import deepcopy

OBJECT_FIELDS=('id','label','kind','state')
CONNECTION_FIELDS=('from','to','label','relation')
WORDING_FIELDS=('title','takeaway','alt')


def _signature_object(obj):
    return {key:obj.get(key) for key in OBJECT_FIELDS}


def _signature_connection(edge):
    return {key:edge.get(key) for key in CONNECTION_FIELDS}


def _scene_signature(scene):
    return dict(title=scene.get('title'),
        objects=[_signature_object(o) for o in scene.get('objects',[]) if isinstance(o,dict)],
        connections=[_signature_connection(c) for c in scene.get('connections',[]) if isinstance(c,dict)])


def _chart_signature(spec):
    payload=spec.get('payload') or {}
    return dict(chart_type=payload.get('chart_type'),
        x_label=payload.get('x_label'),y_label=payload.get('y_label'),
        x_unit=payload.get('x_unit',''),y_unit=payload.get('y_unit',''),
        data_semantics=deepcopy(spec.get('data_semantics')),
        series=[deepcopy(dict(label=s.get('label'),x=s.get('x'),y=s.get('y'),
                 bin_edges=s.get('bin_edges'),counts=s.get('counts')))
                for s in payload.get('series',[]) if isinstance(s,dict)])


def _authorized_paths(issues):
    paths=[]
    for issue in issues:
        if isinstance(issue,dict) and isinstance(issue.get('object_paths'),list):
            paths.extend(p for p in issue['object_paths'] if isinstance(p,str))
    return paths


def _parse_authorizations(paths):
    add_scenes=False;objects=set();edges=set();scene_edits=set()
    for path in paths:
        parts=[part for part in path.split('/') if part]
        if parts[:2]!=['payload','scenes']:continue
        if len(parts)==2:add_scenes=True;continue
        try:index=int(parts[2])
        except ValueError:continue
        if len(parts)==3:scene_edits.add(index);continue
        if parts[3] in ('objects','connections') and len(parts)>=5:
            try:target=(index,int(parts[4]))
            except ValueError:continue
            (objects if parts[3]=='objects' else edges).add(target)
    return add_scenes,objects,edges,scene_edits


def build_preservation_manifest(visual,issues=None):
    spec=deepcopy(visual) if isinstance(visual,dict) else {}
    authorized=_authorized_paths(issues)
    manifest=dict(kind=spec.get('kind'),origin=spec.get('origin'),
        title=spec.get('title'),takeaway=spec.get('takeaway'),alt=spec.get('alt'),
        refs=deepcopy(spec.get('refs',[])),
        presentation=deepcopy(spec.get('presentation')),
        authorized=sorted(set(authorized)))
    payload=spec.get('payload') or {}
    if spec.get('kind')=='story':
        layout=payload.get('layout') or 'scenes'
        manifest.update(layout=layout,ordered=payload.get('ordered',False))
        if layout=='scenes':
            manifest['scenes']=[_scene_signature(s) for s in payload.get('scenes') or [] if isinstance(s,dict)]
        elif layout=='pairwise_match':
            manifest['pairwise']=dict(items=[deepcopy(dict(id=i.get('id'),label=i.get('label'),detail=i.get('detail')))
                    for i in payload.get('items') or [] if isinstance(i,dict)],
                order=list(payload.get('order') or []),rows=deepcopy(payload.get('rows')),
                reference_label=payload.get('reference_label'),observed_label=payload.get('observed_label'))
        elif layout=='feedback_trace':
            manifest['feedback']=dict(example_label=payload.get('example_label'),scope_note=payload.get('scope_note'),
                choices=deepcopy(payload.get('choices')),criteria=deepcopy(payload.get('criteria')),
                turns=[deepcopy(t) for t in payload.get('turns') or [] if isinstance(t,dict)])
    else:
        manifest.update(chart=_chart_signature(spec))
    return manifest


def _candidate_scene(scenes,signature,index):
    for scene in scenes:
        if isinstance(scene,dict) and scene.get('title')==signature.get('title'):return scene
    return scenes[index] if index<len(scenes) else None


def _validate_story(candidate_payload,manifest,add_scenes,objects,edges,scene_edits):
    scenes=candidate_payload.get('scenes') or []
    base=manifest.get('scenes') or []
    if (candidate_payload.get('layout') or 'scenes')!=manifest.get('layout'):
        raise ValueError('Visual preservation: story layout was altered')
    if candidate_payload.get('ordered',False)!=manifest.get('ordered'):
        raise ValueError('Visual preservation: story ordering was altered')
    if len(scenes)<len(base):
        raise ValueError('Visual preservation: baseline story scenes were removed')
    for index,signature in enumerate(base):
        target=_candidate_scene([s for s in scenes if isinstance(s,dict)],signature,index)
        if target is None:
            raise ValueError('Visual preservation: baseline story scene is missing')
        if target.get('title')!=signature.get('title') and index not in scene_edits:
            raise ValueError('Visual preservation: scene title was altered')
        baseline_objects=[_signature_object(o) for o in signature['objects']]
        candidate_objects=[_signature_object(o) for o in target.get('objects',[]) if isinstance(o,dict)]
        if len(candidate_objects)<len(baseline_objects):
            raise ValueError('Visual preservation: baseline objects were removed')
        for order,signature_object in enumerate(baseline_objects):
            match=[o for o in candidate_objects if o.get('id')==signature_object.get('id')]
            if not match:
                raise ValueError(f"Visual preservation: object {signature_object.get('id')} was removed")
            current=match[0]
            if current!=signature_object:
                authorized=(index,order) in objects or index in scene_edits
                if not authorized:
                    raise ValueError(f"Visual preservation: object {signature_object.get('id')} was altered without authorization")
                if current.get('id')!=signature_object.get('id') or current.get('kind')!=signature_object.get('kind'):
                    raise ValueError(f"Visual preservation: object {signature_object.get('id')} identity was altered")
        baseline_edges=[_signature_connection(c) for c in signature['connections']]
        candidate_edges=[_signature_connection(c) for c in target.get('connections',[]) if isinstance(c,dict)]
        if len(candidate_edges)<len(baseline_edges):
            raise ValueError('Visual preservation: baseline connections were removed')
        for order,signature_edge in enumerate(baseline_edges):
            if signature_edge in candidate_edges:continue
            exact=[c for c in candidate_edges if (c.get('from'),c.get('to'))==(signature_edge.get('from'),signature_edge.get('to'))]
            authorized=(index,order) in edges or index in scene_edits
            if authorized and len(exact)==1 and (exact[0].get('from'),exact[0].get('to'),exact[0].get('relation'))==(signature_edge.get('from'),signature_edge.get('to'),signature_edge.get('relation')):
                continue
            raise ValueError(f"Visual preservation: connection {signature_edge.get('from')}->{signature_edge.get('to')} was removed or altered without authorization")


def _validate_pairwise(candidate_payload,manifest,paths):
    base=manifest.get('pairwise') or {}
    if candidate_payload.get('reference_label')!=base.get('reference_label') or candidate_payload.get('observed_label')!=base.get('observed_label'):
        raise ValueError('Visual preservation: pairwise labels were altered')
    if candidate_payload.get('rows')!=base.get('rows'):
        raise ValueError('Visual preservation: pairwise rows were altered')
    order_edit='/payload/order' in paths
    if list(candidate_payload.get('order') or [])!=list(base.get('order') or []) and not order_edit:
        raise ValueError('Visual preservation: pairwise order was altered without authorization')
    baseline=base.get('items') or []
    candidates=[i for i in candidate_payload.get('items') or [] if isinstance(i,dict)]
    if len(candidates)<len(baseline):
        raise ValueError('Visual preservation: baseline pairwise items were removed')
    for index,signature in enumerate(baseline):
        match=[i for i in candidates if i.get('id')==signature.get('id')]
        if not match:
            raise ValueError(f"Visual preservation: pairwise item {signature.get('id')} was removed")
        current=match[0]
        if {k:current.get(k) for k in ('label','detail')}!={k:signature.get(k) for k in ('label','detail')}:
            authorized=f'/payload/pairs/items/{index}' in paths
            if not authorized:
                raise ValueError(f"Visual preservation: pairwise item {signature.get('id')} was altered without authorization")
            if current.get('id')!=signature.get('id'):
                raise ValueError(f"Visual preservation: pairwise item {signature.get('id')} identity was altered")


def _validate_feedback(candidate_payload,manifest,paths):
    base=manifest.get('feedback') or {}
    for key in ('example_label','scope_note','choices','criteria'):
        if candidate_payload.get(key)!=base.get(key):
            raise ValueError(f'Visual preservation: feedback {key} was altered')
    baseline=base.get('turns') or []
    candidates=[t for t in candidate_payload.get('turns') or [] if isinstance(t,dict)]
    if len(candidates)<len(baseline):
        raise ValueError('Visual preservation: baseline feedback turns were removed')
    for index,signature in enumerate(baseline):
        target=candidates[index] if index<len(candidates) else None
        if target is None or target.get('id')!=signature.get('id'):
            raise ValueError(f'Visual preservation: feedback turn {signature.get("id")} is missing or reordered')
        if deepcopy(target)!=deepcopy(signature) and f'/payload/turns/{index}' not in paths:
            raise ValueError(f'Visual preservation: feedback turn {index} was altered without authorization')


def _validate_chart(candidate,manifest):
    chart=manifest.get('chart') or {}
    payload=candidate.get('payload') or {}
    for key in ('chart_type','x_label','y_label','x_unit','y_unit'):
        if payload.get(key)!=chart.get(key):
            raise ValueError(f'Visual preservation: chart {key} was altered')
    if candidate.get('data_semantics')!=chart.get('data_semantics'):
        raise ValueError('Visual preservation: chart data_semantics was altered')
    baseline=chart.get('series') or []
    candidate_series=payload.get('series') or []
    if len(candidate_series)<len(baseline):
        raise ValueError('Visual preservation: baseline chart series were removed')
    for index,signature in enumerate(baseline):
        if index>=len(candidate_series):break
        current=candidate_series[index]
        for key in ('label','x','y','bin_edges','counts'):
            if current.get(key)!=signature.get(key):
                raise ValueError(f'Visual preservation: series {index} {key} was altered')


def validate_preserved_visual(candidate,manifest):
    if not isinstance(candidate,dict):
        raise ValueError('Visual preservation: candidate must be an object')
    authorized=set(manifest.get('authorized') or [])
    checks=(('kind',manifest.get('kind')),('origin',manifest.get('origin')))
    for key,expected in checks:
        if candidate.get(key)!=expected:
            raise ValueError(f'Visual preservation: {key} was altered')
    for key in WORDING_FIELDS:
        if candidate.get(key)!=manifest.get(key) and '/'+key not in authorized:
            raise ValueError(f'Visual preservation: {key} was altered')
    if candidate.get('refs',[])!=manifest.get('refs',[]):
        raise ValueError('Visual preservation: refs were altered')
    if candidate.get('presentation')!=manifest.get('presentation'):
        raise ValueError('Visual preservation: presentation was altered')
    add_scenes,objects,edges,scene_edits=_parse_authorizations(manifest.get('authorized') or [])
    payload=candidate.get('payload') or {}
    if manifest.get('kind')=='story':
        layout=(payload.get('layout') or 'scenes') if isinstance(payload,dict) else 'scenes'
        if layout!=(manifest.get('layout') or 'scenes'):
            raise ValueError('Visual preservation: story layout was altered')
        if layout=='pairwise_match':_validate_pairwise(payload,manifest,authorized)
        elif layout=='feedback_trace':_validate_feedback(payload,manifest,authorized)
        else:_validate_story(payload,manifest,add_scenes,objects,edges,scene_edits)
    else:
        _validate_chart(candidate,manifest)
