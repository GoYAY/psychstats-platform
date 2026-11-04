"""Non-public bounded files and idempotent expiry sweeps."""
from pathlib import Path
import hashlib,os,re,shutil,tempfile
from .config import OnlineError,_path
from .store import TERMINAL

class PrivateFiles:
    def __init__(self,root):
        self.root=_path(str(Path(root).absolute()));self.root.mkdir(parents=True,exist_ok=True,mode=0o700)

    def path_for(self,job_id,asset_id):
        for value in (job_id,asset_id):
            if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}(?:\.[a-z0-9]{1,8})?',value):
                raise OnlineError('invalid_file','文件标识无效。')
        path=self.root/job_id/asset_id
        for p in (self.root,self.root/job_id,path):
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise OnlineError('invalid_file','文件路径不安全。')
        if not path.resolve().is_relative_to(self.root):raise OnlineError('invalid_file','文件路径越界。')
        return path

    def put(self,job_id,source_id,stream,limits):
        path=self.path_for(job_id,source_id);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        digest=hashlib.sha256();count=0;temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.part',delete=False) as target:
                temp=Path(target.name)
                while True:
                    part=stream.read(min(65536,limits.max_file_bytes+1-count))
                    if not part:break
                    count+=len(part)
                    if count>limits.max_file_bytes:raise OnlineError('file_too_large','文件超过本轮限制。',413)
                    target.write(part);digest.update(part)
                target.flush();os.fsync(target.fileno())
            os.replace(temp,path)
        finally:
            if temp is not None:temp.unlink(missing_ok=True)
        return dict(asset_id=source_id,sha256=digest.hexdigest(),bytes=count)

    def remove_job(self,job_id):
        path=self.path_for(job_id,'placeholder').parent
        if path.exists():shutil.rmtree(path)

    def archive_job(self,job_id):
        path=self.path_for(job_id,'placeholder').parent
        if not path.exists():return False
        target=self.root/'archive'/job_id
        if target.exists():shutil.rmtree(target)
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.replace(path,target);return True

def cleanup_jobs(store,files,now):
    errors=[]
    with store.transaction() as db:
        from json import loads
        for row in db.execute('SELECT body FROM jobs').fetchall():
            job=loads(row['body'])
            if job['state'] not in TERMINAL and now-job['updated_at']>604800:
                job.update(state='expired',terminal_at=now,updated_at=now,version=job['version']+1,lease_token=None,lease_until=None)
                store._write(db,job)
            terminal=job.get('terminal_at')
            if terminal is not None and now-terminal>604800:
                try:files.archive_job(job['id'])
                except OSError:errors.append(job['id']);continue
                job.update(manifest={},checkpoint=None,question=None,result=None,progress=None)
                store._write(db,job)
        db.execute('DELETE FROM audit WHERE at<?',(now-30*86400,))
        db.execute('DELETE FROM sessions WHERE expires<?',(now,))
    return errors
