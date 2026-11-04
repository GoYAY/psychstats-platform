"""Fail-closed configuration; no provider credentials in serializable config."""
from dataclasses import dataclass,fields
from pathlib import Path
from urllib.parse import urlsplit
import re

class OnlineError(Exception):
    def __init__(self,code,message,status=400):
        super().__init__(message);self.code=code;self.message=message;self.status=status

@dataclass(frozen=True)
class Limits:
    max_job_calls:int
    max_daily_calls:int
    max_job_tokens:int
    max_daily_tokens:int
    max_output_tokens:int
    max_job_network_calls:int
    max_daily_network_calls:int
    max_file_bytes:int
    max_total_bytes:int
    max_files:int
    max_pages:int
    max_text_chars:int
    max_task_seconds:int
    max_queue:int
    request_timeout:int

@dataclass(frozen=True)
class OnlineConfig:
    private_root:Path
    public_root:Path
    origin:str
    api_prefix:str
    limits:Limits
    figure_qa_dir:Path|None=None
    cjk_font:Path|None=None
    generation_enabled:bool=False
    visual_intent_enabled:bool=False

def _path(value):
    if not value or not Path(value).is_absolute():raise OnlineError('invalid_config','必须配置绝对数据目录。')
    p=Path(value)
    if any(q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction()) for q in [p,*p.parents]):
        raise OnlineError('invalid_config','数据目录不得经过符号链接。')
    return p.resolve()

def load_config(environ):
    private=_path(environ.get('TERM_PRIVATE_ROOT'));public=_path(environ.get('TERM_PUBLIC_ROOT'))
    if private.is_relative_to(public) or public.is_relative_to(private):
        raise OnlineError('invalid_config','私有目录必须与静态发布目录隔离。')
    origin=environ.get('TERM_ORIGIN','')
    try:p=urlsplit(origin);port=p.port
    except ValueError:raise OnlineError('invalid_config','网站来源配置无效。') from None
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or (port is not None and not 1<=port<=65535) or any(c.isspace() for c in origin):
        raise OnlineError('invalid_config','网站来源必须是确切HTTPS来源。')
    prefix=environ.get('TERM_API_PREFIX','')
    if not re.fullmatch(r'/(?:[a-zA-Z0-9_-]+/)+',prefix):raise OnlineError('invalid_config','API路径配置无效。')
    values={}
    for field in fields(Limits):
        value=environ.get('TERM_'+field.name.upper(),'')
        if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]{0,9}',value):
            raise OnlineError('invalid_config','必须显式配置所有生成安全限额。')
        values[field.name]=int(value)
    limits=Limits(**values)
    if (limits.max_files>100 or limits.max_pages>10000 or limits.max_file_bytes>128*1024*1024
        or limits.max_total_bytes>512*1024*1024 or limits.max_output_tokens>32768
        or limits.request_timeout>300 or limits.max_task_seconds>86400
        or limits.max_job_calls>limits.max_daily_calls or limits.max_job_tokens>limits.max_daily_tokens
        or limits.max_job_network_calls>limits.max_daily_network_calls
        or limits.max_file_bytes>limits.max_total_bytes):
        raise OnlineError('invalid_config','生成限额超出支持范围或相互矛盾。')
    qa=_path(environ['TERM_FIGURE_QA_DIR']) if environ.get('TERM_FIGURE_QA_DIR') else None
    font=_path(environ['TERM_CJK_FONT']) if environ.get('TERM_CJK_FONT') else None
    enabled=environ.get('TERM_GENERATION_ENABLED','false')
    if enabled not in ('true','false'):raise OnlineError('invalid_config','生成开关必须为true或false。')
    visual=environ.get('TERM_VISUAL_INTENT_ENABLED','false')
    if visual not in ('true','false'):raise OnlineError('invalid_config','图示意图开关必须为true或false。')
    return OnlineConfig(private,public,origin,prefix,limits,qa,font,enabled=='true',visual=='true')
