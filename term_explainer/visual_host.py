"""Capabilities are selected by trusted host code, never copied from a lesson."""
def visual_host_capabilities(value=None,*,policy_version=0):
    result=dict(static_visuals=True,interactive_visuals=False,model_code_allowed=False)
    if value is not None:
        if not isinstance(value,dict) or set(value)!={'interactive_chart_types'} or value['interactive_chart_types']!=['bar']:
            raise ValueError('Only the validated bar host is available')
        result.update(interactive_visuals=True,interactive_chart_types=['bar'])
    if policy_version:
        if type(policy_version) is not int or policy_version!=1:raise ValueError('Unsupported visual policy')
        result.update(presentation_version=1,layouts=dict(bar={'single_series':['single'],'multi_series':['grouped','facets']},histogram={'single_series':['single'],'multi_series':['overlay','facets']},line={'single_series':['single'],'multi_series':['overlay']},scatter={'single_series':['single'],'multi_series':['overlay']},story=['story']),inspection=dict(chart_type='bar',numeric_role='exact',layouts=['single','grouped'],nonnegative_finite_values=True,unique_display_categories=True,title_max=120,takeaway_max=400,category_max=24,series_label_max=24,axis_label_unit_max=40) if value else None)
    return result
