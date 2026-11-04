from tests.term_explainer.helpers import request_payload,result_payload
def quality_case():
    request=request_payload();lesson=result_payload()
    lesson['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none')
    return request,lesson
