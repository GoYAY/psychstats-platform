"""Bounded DeepSeek HTTPS adapter. Tests replace HTTP, never real behavior."""
from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPException, IncompleteRead
import hashlib
import ipaddress
import json
import os
import re
from ssl import SSLError
from threading import Lock
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .literature import _doi

def has_teaching_chapter_body(text):
    """A substantive teaching chapter need not have research-paper sections.

    This is an eligibility signal only: identity and located claim checks still
    apply. Neither learning-objective navigation alone nor an abstract qualifies.
    """
    if not isinstance(text,str) or len(text)<1000:return False
    heading=r'(?mi)^\s*(?:#{1,6}\s*)?(?:%s)\s*#*\s*$'
    return (not re.search(heading%r'abstract|摘要',text)
        and bool(re.search(heading%r'prerequisites|先修知识|预备知识',text))
        and bool(re.search(heading%r'learning objectives|learning outcomes|学习目标|教学目标',text)))


class DeepSeekError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class ModelReply:
    content: str
    model: str
    usage: dict
    finish_reason: str

def parse_model_reply(value):
    try:
        choice=value['choices'][0]
        content,finish=choice['message']['content'],choice['finish_reason']
        model,usage=value['model'],value.get('usage',{})
    except (KeyError,IndexError,TypeError):raise DeepSeekError('invalid_provider_response','模型响应缺少必要字段。') from None
    if finish=='length':raise DeepSeekError('model_truncated','模型未完整交付内容，请调整输入后再试。')
    if finish!='stop':raise DeepSeekError('model_incomplete','模型未正常结束；请检查记录的结束原因，不自动重试。')
    if not isinstance(content,str) or not content.strip():raise DeepSeekError('empty_model_response','模型未返回可用内容。')
    if not isinstance(model,str) or not isinstance(usage,dict):raise DeepSeekError('invalid_provider_response','模型用量或标识格式无效。')
    return ModelReply(content,model,usage,finish)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _complete_interrupted_receipt(data):
    """Recover only a complete completion envelope, never finish missing text."""
    if not isinstance(data,bytes) or not 0<len(data)<=4*1024*1024:return None
    def unique(pairs):
        if len({k for k,v in pairs})!=len(pairs):raise ValueError('duplicate JSON key')
        return dict(pairs)
    def invalid(value):raise ValueError('nonfinite JSON number')
    try:
        value=json.loads(data,object_pairs_hook=unique,parse_constant=invalid)
        if (not isinstance(value,dict) or value.get('object')!='chat.completion'
            or not isinstance(value.get('id'),str) or not 1<=len(value['id'])<=256
            or not isinstance(value.get('model'),str) or not value['model']):return None
        usage=value.get('usage');choices=value.get('choices')
        if (not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens'))
            or usage['prompt_tokens']+usage['completion_tokens']!=usage['total_tokens']
            or not isinstance(choices,list) or len(choices)!=1):return None
        choice=choices[0]
        if (not isinstance(choice,dict) or type(choice.get('index')) is not int or choice['index']!=0
            or choice.get('finish_reason') not in ('stop','length','content_filter','insufficient_system_resource')):return None
        message=choice.get('message')
        if not isinstance(message,dict) or message.get('role')!='assistant' or not isinstance(message.get('content'),str):return None
        value['_transport_recovery']=dict(kind='IncompleteRead',received_bytes=len(data),basis='complete_json_completion_and_usage')
        return value
    except (ValueError,UnicodeError,TypeError,RecursionError):return None


def _transport(url, payload, headers, timeout):
    request = Request(url, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'),
                      headers=headers, method='POST')
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data)>4*1024*1024:raise DeepSeekError('response_too_large','供应商响应超过开发阶段限制。')
            remaining=getattr(response,'length',None)
            if type(remaining) is int and remaining>0:raise IncompleteRead(data,remaining)
        if len(data) > 4 * 1024 * 1024:
            raise DeepSeekError('response_too_large', '供应商响应超过开发阶段限制。')
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError('response must be an object')
        return value
    except HTTPError as error:
        failure=DeepSeekError(f'provider_http_{error.code}', f'供应商请求失败（HTTP {error.code}）。')
        # Keep the vendor's own explanation: a rejected request cannot be fixed blind.
        try:detail=error.read(2000).decode('utf-8','replace')
        except Exception:detail=''
        failure.provider_detail=detail
        raise failure from None
    except TimeoutError:
        raise DeepSeekError('provider_timeout', '供应商请求超时。') from None
    except URLError:
        raise DeepSeekError('provider_unavailable', '暂时无法连接供应商。') from None
    except (HTTPException, ConnectionError, SSLError) as cause:
        error=DeepSeekError('provider_connection_interrupted', '供应商连接中断，响应及用量尚未确认；未自动重试。')
        partial=cause.partial if isinstance(cause,IncompleteRead) else b''
        prefix_bytes=len(partial)
        # CPython _read_chunked wraps _safe_read: outer.partial is previous
        # complete chunks; the explicit cause holds the interrupted last chunk.
        nested=cause.__cause__ if isinstance(cause,IncompleteRead) else None
        inner=nested.partial if isinstance(nested,IncompleteRead) and isinstance(nested.partial,bytes) else b''
        received_bytes=prefix_bytes+len(inner)
        partial=partial+inner if received_bytes<=4*1024*1024 else b''
        if isinstance(cause,IncompleteRead) and urlsplit(url).path=='/chat/completions':
            recovered=_complete_interrupted_receipt(partial)
            if recovered is not None:return recovered
        error.transport_info=dict(kind='IncompleteRead' if isinstance(cause,IncompleteRead) else 'HTTPException' if isinstance(cause,HTTPException) else 'SSLError' if isinstance(cause,SSLError) else 'ConnectionError',partial_bytes=received_bytes,completed_chunk_bytes=prefix_bytes,interrupted_chunk_bytes=len(inner))
        # Private diagnostic only. Never accept a partial body as a model receipt.
        if isinstance(partial,bytes) and 0<len(partial)<=4*1024*1024:error.partial_response=partial
        raise error from None
    except (ValueError, UnicodeError):
        raise DeepSeekError('invalid_provider_response', '供应商响应格式无效。') from None


def safe_public_url(url):
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
        raise ValueError('invalid public source URL')
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower().rstrip('.')
        port = parsed.port
    except ValueError:
        raise ValueError('invalid source URL') from None
    if (parsed.scheme != 'https' or not host or parsed.username or parsed.password
            or port not in (None, 443) or host == 'localhost' or '.' not in host
            or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid'))
            or '%' in host or '\\' in url):
        raise ValueError('only public HTTPS source URLs without credentials are allowed')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('literal IP sources are not allowed')
    return url


def _search_doi_hints(url, title):
    """Parse URL components before decoding; every hint remains unverified metadata."""
    parsed = urlsplit(url)
    try:
        parameters = parse_qs(parsed.query, max_num_fields=128)
    except ValueError:
        parameters = {}
    raw = [value for key, values in parameters.items() if key.casefold() == 'doi' for value in values]
    match = re.search(r'10\.\d{4,9}/[^\s?#<>]+', unquote(parsed.path))
    if match:
        raw.append(match.group())
    raw.extend(re.findall(r'\bdoi\s*:\s*(10\.\d{4,9}/[^\s<>]+)', title, re.I))
    hints = set()
    for value in raw:
        value = value.strip().rstrip('.,;，。')
        while value.endswith(')') and value.count(')') > value.count('('):
            value = value[:-1]
        try:
            normalized = _doi(value)
        except ValueError:
            continue
        if normalized:
            hints.add(normalized)
    return sorted(hints)


class DeepSeekClient:
    supports_receipt=True
    def __init__(self, *, api_key=None, model=None, max_calls=0, transport=None,max_tokens=8192,timeout=90):
        if max_calls is not None and (type(max_calls) is not int or max_calls < 0):
            raise ValueError('max_calls must be a non-negative integer')
        self._key = api_key if api_key is not None else os.environ.get('DEEPSEEK_API_KEY', '')
        self.model = model or os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash')
        self.max_calls, self.calls = max_calls, 0
        if type(max_tokens) is not int or not 1<=max_tokens<=32768 or type(timeout) not in (int,float) or not 1<=timeout<=300:
            raise ValueError('invalid response window or timeout')
        self.max_tokens,self.timeout=max_tokens,timeout
        self._transport, self._lock = transport or _transport, Lock()
        self.metrics = []

    def _call(self, path, payload, *, receipt=None):
        if not self._key:
            raise DeepSeekError('missing_credentials', '尚未配置本轮开发使用的模型密钥。')
        with self._lock:
            if self.max_calls is not None and self.calls >= self.max_calls:
                raise DeepSeekError('call_budget_exhausted', '本轮开发调用次数已达到上限。')
            self.calls += 1
            event = dict(kind=path.rsplit('/', 1)[-1], attempt=self.calls, outcome='started')
            self.metrics.append(event)
        started = perf_counter()
        try:
            result = self._transport('https://api.deepseek.com' + path, payload,
                {'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json'}, self.timeout)
            if receipt is not None:receipt(result)
            if not isinstance(result, dict):
                raise DeepSeekError('invalid_provider_response', '供应商返回了无效结构。')
            # Receipt is not proof of a valid model answer or a correctly read paper.
            event['outcome'] = 'response_received'
            if path == '/chat/completions':
                choices = result.get('choices')
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    finish = choices[0].get('finish_reason')
                    event['finish_reason'] = finish if finish in ('stop','length','content_filter','tool_calls','insufficient_system_resource') else 'unrecognized'
                usage = result.get('usage', {})
                if isinstance(usage, dict):
                    safe_usage = {key: usage[key] for key in ('prompt_tokens','completion_tokens','total_tokens')
                                  if type(usage.get(key)) is int and usage[key] >= 0}
                    for group, key in (('completion_tokens_details','reasoning_tokens'),('prompt_tokens_details','cached_tokens')):
                        details = usage.get(group, {})
                        if isinstance(details, dict) and type(details.get(key)) is int and details[key] >= 0:
                            safe_usage[key] = details[key]
                    event['usage'] = safe_usage
            return result
        except DeepSeekError as error:
            event.update(outcome='failed', error_code=error.code)
            raise
        except Exception:
            event.update(outcome='failed', error_code='unexpected_transport_error')
            raise
        finally:
            event['elapsed_ms'] = round((perf_counter() - started) * 1000, 3)

    def generate(self, messages: list[dict], *, receipt=None, reasoning_effort: str = 'high') -> ModelReply:
        if reasoning_effort not in ('low','high'):reasoning_effort='high'
        value = self._call('/chat/completions', dict(model=self.model, messages=messages,
            response_format={'type': 'json_object'}, reasoning_effort=reasoning_effort, max_tokens=self.max_tokens),receipt=receipt)
        return parse_model_reply(value)

    def search(self, query: str) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 128:
            raise ValueError('search query must contain 1 to 128 characters')
        value = self._call('/v1/tools/search', dict(query=query, count=5, need_content=False))
        if not isinstance(value.get('results'), list):
            raise DeepSeekError('invalid_provider_response', '检索结果格式无效。')
        candidates = []
        for item in value['results']:
            if not isinstance(item, dict) or not isinstance(item.get('title'), str):
                continue
            try:
                url = safe_public_url(item.get('url'))
            except ValueError:
                continue
            doi_hints = _search_doi_hints(url, item['title'])
            candidates.append(dict(id='found-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                title=item['title'], doi=doi_hints[0] if len(doi_hints) == 1 else '',
                doi_basis='search_metadata_unverified', doi_conflict=len(doi_hints) > 1,
                doi_hints=doi_hints, url=url, text='', scope='metadata',
                origin='search', search_summary=item.get('summary', ''),
                search_snippet=item.get('snippet', ''), authority=item.get('authority', -1), references=[]))
        return candidates

    def fetch(self, url: str, *, source_id: str, origin='search') -> dict:
        safe_public_url(url)
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError('source_id is required')
        if origin not in {'search', 'reference'}:
            raise ValueError('invalid fetched source origin')
        value = self._call('/v1/tools/fetch', {'url': url})
        text = value.get('content', '')
        if not isinstance(text, str) or not text.strip():
            raise DeepSeekError('source_unavailable', '未取得可阅读正文，不能将该资料记为已读。')
        if len(text) < 2000 and re.search(r'checking your browser|recaptcha|verify you are human|请输入验证码', text[:512], re.I):
            raise DeepSeekError('source_access_blocked', '该资料需要访问验证，请提供合法可读版本。')
        # A page fetch is not proof that the whole research article was obtained.
        heading = r'(?mi)^\s*(?:#{1,6}\s*)?(?:\d+[.)]?\s+)?%s\s*#*\s*$'
        body_sections = re.findall(heading % r'(introduction|materials and methods|methods?|methodology|results?|discussion|conclusions?|方法|结果|讨论|引言|研究方法)', text)
        has_abstract = bool(re.search(heading % r'(abstract|摘要)', text))
        restricted = re.search(r'get full access|purchase access|restricted access|购买全文', text, re.I)
        # Absence of a paywall notice is not evidence that a page contains the body.
        # This structural signal is not a semantic review of the reported method.
        body_detected = len(set(section.casefold() for section in body_sections)) >= 2
        scope = 'abstract' if not body_detected and (has_abstract or (restricted and re.search(r'abstract|摘要', text, re.I))) else 'excerpt'
        teaching_body=scope=='excerpt' and has_teaching_chapter_body(text)
        return dict(id=source_id, title=value.get('title') or '已取得的来源片段', doi='', url=url,
                    text=text, scope=scope, origin=origin, references=[],
                    technical_evidence_eligible=body_detected or teaching_body,
                    scope_basis='body_sections_detected' if body_detected else 'teaching_chapter_body_detected' if teaching_body else 'abstract_heading' if scope == 'abstract' else 'unclassified_fetched_text')
