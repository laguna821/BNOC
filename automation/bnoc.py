"""BNOC local automation CLI. Does not generate theological claims or simulate image tools."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from bible import Bible, digest, save, fetch, ALIASES
import bulletin
import render

DEFAULT_CONFIG=Path(os.environ.get('BNOC_CONFIG',str(Path.home()/'Achmage-System/bnoc/config.json')))
STAGES=['discovered','passage-confirmed','researched','written','illustrated','rendered','validated','pushed','published']
REVIEW_KEYS=['historicalAccuracy','originalLanguages','orthodoxyOrthopraxy','layReadability','citationsChecked','visualAccuracy','mobileLightDark','searchNotesDownload','printLayout']

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def config(path):
    c=load(path);c['root']=Path(c['stateRoot']);c['repo']=Path(c['repository'])
    for private in (c['root'],Path(c['bible'])):
        if private.resolve().is_relative_to(c['repo'].resolve()):raise ValueError('Private Bible and state must stay outside the public repository')
    return c

@contextlib.contextmanager
def guard(root):
    root.mkdir(parents=True,exist_ok=True);path=root/'command.lock'
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
    try:
        if os.name=='nt':
            import msvcrt
            if os.fstat(fd).st_size==0:os.write(fd,b'0')
            os.lseek(fd,0,0);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)

def state(c):
    path=c['root']/'state.json'
    return load(path) if path.exists() else {'schemaVersion':1,'issues':{},'observations':{},'failures':{}}
def runpath(c,key):
    if not re.fullmatch(r'[a-z0-9-]+',key):raise ValueError('Invalid run ID')
    return c['root']/'runs'/key
def identity(date,service,selected):
    dt.date.fromisoformat(date)
    return date+'-'+digest([service,selected])[:16]
def make_run(c,reference,date,service,mode):
    bible=Bible(c['bible'],c['root']/'cache')
    selected=bible.parse(reference);key=identity(date,service,selected);s=state(c)
    if key in s['issues'] and s['issues'][key]['stage']=='published':return dict(status='already-published',runId=key,**s['issues'][key])
    path=runpath(c,key);path.mkdir(parents=True,exist_ok=True)
    if (path/'run.json').exists():
        run=load(path/'run.json')
        if mode=='draft' and run['mode']=='publish':raise ValueError('Existing publishing run; use its status')
        return dict(status='resume',runId=key,stage=run['stage'],path=str(path))
    code=ALIASES[selected[0][0]]['code'];slug=re.sub('[^a-z0-9-]','-',code)
    filename=f'{slug}-{selected[0][1]}-{selected[0][2]}-{digest(selected)[:8]}.html'
    day=dt.date.fromisoformat(date);relative=f'{day.year}/{day:%m%d%Y}/{filename}'
    run=dict(schemaVersion=1,id=key,date=date,reference=reference,service=service,selected=selected,mode=mode,stage='discovered',relativePath=relative,createdAt=dt.datetime.now(dt.timezone.utc).isoformat(),attempts=[],versions={'skill':'1.0','template':'bnoc-reader-1.0'},lease=None)
    save(path/'run.json',run);s['issues'][key]=dict(stage='discovered',relativePath=relative,reference=reference,date=date,service=service);save(c['root']/'state.json',s)
    return dict(status='created',runId=key,path=str(path),relativePath=relative)

def owned(c,key,token):
    path=runpath(c,key);run=load(path/'run.json');lease=run.get('lease')
    if not lease or lease['token']!=token or lease['expires']<time.time():raise ValueError('Valid run lease required; claim or explicitly resume first')
    return path,run
def advance(c,path,run,stage):
    run['stage']=stage
    if run.get('lease'):run['lease']['expires']=time.time()+21600
    save(path/'run.json',run);s=state(c);s['issues'][run['id']].update(stage=stage,updatedAt=dt.datetime.now(dt.timezone.utc).isoformat())
    save(c['root']/'state.json',s)

def check(c,force=False):
    now=dt.datetime.now(bulletin.KST)
    if not force and not bulletin.due(now):return {'status':'outside-window'}
    items=bulletin.discover();target=bulletin.target_sunday(now)
    # At most the newest due issue, including one missed Sunday after host downtime.
    eligible=[x for x in items if dt.date.fromisoformat(x['date'])<=target]
    if not eligible:return {'status':'not-posted','targetDate':target.isoformat()}
    candidate=bulletin.details(eligible[0]);s=state(c)
    downloaded=[]
    folder=c['root']/'bulletins'/candidate['id'];folder.mkdir(parents=True,exist_ok=True)
    for i,url in enumerate(candidate['images']):
        # Re-read images to detect edits at the same URL, not just URL changes.
        data=fetch(url);name=f'{i+1:02d}-{digest(data)[:16]}.jpg';path=folder/name
        if not path.exists():path.write_bytes(data)
        downloaded.append(dict(url=url,path=str(path),sha256=digest(data)))
    candidate['imageFiles']=downloaded;candidate['contentSha256']=digest([x['sha256'] for x in downloaded])
    save(folder/'candidate.json',candidate)
    old=s['observations'].get(candidate['id'])
    if old and old.get('contentSha256')==candidate['contentSha256']:
        issue=s['issues'].get(old.get('runId'),{})
        if issue.get('stage')=='published':return dict(status='already-published',date=candidate['date'],url=issue.get('url'))
        return dict(status='resume-required',runId=old.get('runId'),stage=issue.get('stage'),candidate=str(folder/'candidate.json'))
    return dict(status='needs-image-reading',candidate=str(folder/'candidate.json'),date=candidate['date'],images=downloaded)

def audit_review(path,run):
    manuscript=load(path/'manuscript.json');passage=load(path/'passage.json')
    report=load(path/'review.json');output=path/Path(run['relativePath']).name
    binding={'manuscriptSha256':digest(manuscript),'passageSha256':passage['sha256'],'htmlSha256':digest(output.read_bytes())}
    for k,v in binding.items():
        if report.get(k)!=v:raise ValueError('Stale review: '+k)
    if manuscript.get('date')!=run['date']:raise ValueError('Manuscript date differs from issue')
    rebuilt,_=render.render(manuscript,passage,path,run['id'],output.name)
    if digest(rebuilt.encode())!=binding['htmlSha256']:raise ValueError('Re-render required: figures or renderer changed')
    if report.get('blockingFindings'):raise ValueError('Unresolved review findings')
    if not report.get('model') or not report.get('reviewedAt'):raise ValueError('Record actual reviewer model and time')
    for key in REVIEW_KEYS:
        value=report.get('checks',{}).get(key,{})
        if value.get('passed') is not True or not value.get('evidence'):raise ValueError('Review incomplete: '+key)
    if set(report.get('checkedSourceIds',[]))!={s['id'] for s in manuscript['sources']}:raise ValueError('Each source must be actually checked')
    render.validate(manuscript,passage,path)
    return binding

def git(repo,*args,input=None,env=None):
    return subprocess.check_output(['git','-c','core.protectNTFS=false',*args],cwd=repo,input=input,env=env).decode().strip()

def publish(c,path,run):
    if run['mode']!='publish':raise ValueError('Draft mode cannot publish')
    binding=audit_review(path,run);repo=c['repo']
    # No whole-directory add. Preserve every remote tree entry, including Windows-invalid historical names.
    git(repo,'fetch','origin','main')
    base=git(repo,'rev-parse','origin/main')
    relative=run['relativePath'];manifest=f'issues/{run["id"]}.json';data=(path/Path(relative).name).read_bytes()
    existing=subprocess.run(['git','show',base+':'+manifest],cwd=repo,capture_output=True)
    if existing.returncode==0:
        previous=json.loads(existing.stdout)
        if previous['htmlSha256']!=binding['htmlSha256']:raise ValueError('Published issue differs; explicit revision required')
        run['commit']=previous.get('commit',base);advance(c,path,run,'pushed')
        return {'status':'already-pushed','commit':run['commit'],'url':c['site']+relative}
    collision=subprocess.run(['git','cat-file','-e',base+':'+relative],cwd=repo,capture_output=True)
    if collision.returncode==0:raise ValueError('Refusing to overwrite an existing document')
    record=dict(id=run['id'],date=run['date'],reference=run['reference'],service=run['service'],relativePath=relative,**binding,versions=run['versions'],reviewModel=load(path/'review.json')['model'])
    with tempfile.TemporaryDirectory(prefix='bnoc-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'))
        git(repo,'read-tree',base,env=env)
        for target,blob in [(relative,data),(manifest,json.dumps(record,ensure_ascii=False,indent=2).encode())]:
            sha=git(repo,'hash-object','-w','--stdin',input=blob,env=env)
            git(repo,'update-index','--add','--cacheinfo','100644',sha,target,env=env)
        tree=git(repo,'write-tree',env=env)
        # Attribution comes from explicit configured repository owner, never a guessed identity.
        commit=git(repo,'-c','user.name='+c['gitAuthor']['name'],'-c','user.email='+c['gitAuthor']['email'],'commit-tree',tree,'-p',base,input=f'Publish BNOC {run["date"]}: {run["reference"]}\n'.encode(),env=env)
        run['pendingCommit']=commit;save(path/'run.json',run)
        git(repo,'push','origin',commit+':refs/heads/main') # fast-forward only; concurrent pushes fail safely
    run['commit']=commit;advance(c,path,run,'pushed')
    return dict(status='pushed-awaiting-deployment',commit=commit,url=c['site']+relative)

def verify_deployment(c,path,run):
    commit=run.get('commit')
    if not commit:raise ValueError('No recorded commit')
    data=json.loads(fetch('https://api.github.com/repos/laguna821/BNOC/actions/runs?head_sha='+commit))
    jobs=[x for x in data['workflow_runs'] if x['name']=='BNOC Pages (hub+feed)']
    if not jobs:return dict(status='waiting-for-workflow',commit=commit)
    job=jobs[0]
    if job['status']!='completed':return dict(status='deploying',workflow=job['html_url'])
    if job['conclusion']!='success':raise ValueError('Deployment failed: '+job['html_url'])
    url=c['site']+run['relativePath'];live=fetch(url)
    expected=(path/Path(run['relativePath']).name).read_bytes()
    if live.replace(b'\r\n',b'\n')!=expected.replace(b'\r\n',b'\n'):return dict(status='waiting-for-live-content',workflow=job['html_url'])
    index=json.loads(fetch(c['site']+'index.json'))['items']
    if not any(run['relativePath'] in x['link'] for x in index):raise ValueError('Document missing from archive')
    advance(c,path,run,'published');s=state(c);s['issues'][run['id']].update(url=url,commit=commit);save(c['root']/'state.json',s)
    run['lease']=None;run['url']=url;save(path/'run.json',run)
    return dict(status='published',url=url,workflow=job['html_url'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=str(DEFAULT_CONFIG))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('audit-bible');ch=sub.add_parser('check');ch.add_argument('--force',action='store_true')
    extract=sub.add_parser('extract');extract.add_argument('reference');extract.add_argument('--output',required=True)
    start=sub.add_parser('start');start.add_argument('reference');start.add_argument('--date',default=dt.datetime.now(bulletin.KST).date().isoformat());start.add_argument('--service',default='manual');start.add_argument('--mode',choices=['draft','publish'],default='draft')
    observe=sub.add_parser('observe');observe.add_argument('candidate');observe.add_argument('observation')
    for name in ['claim','status','promote','passage','render','validate','publish','verify','release','fail','checkpoint']:
        p=sub.add_parser(name);p.add_argument('run_id')
        if name=='claim':
            p.add_argument('--resume-expired',action='store_true');p.add_argument('--owner',required=True)
            p.add_argument('--changed-evidence',default='');p.add_argument('--manual-recovery',action='store_true')
        elif name not in ('status',):p.add_argument('--token',required=True)
        if name=='checkpoint':p.add_argument('--stage',choices=['researched','written','illustrated'],required=True);p.add_argument('--evidence',required=True)
        if name=='render':p.add_argument('--print-proof',action='store_true')
        if name=='fail':p.add_argument('--reason',required=True);p.add_argument('--changed-evidence',default='')
    args=parser.parse_args();c=config(args.config);command=args.command
    with guard(c['root']):
        bible=Bible(c['bible'],c['root']/'cache')
        if command=='audit-bible':result=bible.audit()
        elif command=='check':result=check(c,args.force)
        elif command=='extract':
            result=bible.extract(args.reference);save(args.output,result)
            result={k:v for k,v in result.items() if k!='verses'}
        elif command=='start':result=make_run(c,args.reference,args.date,args.service,args.mode)
        elif command=='observe':
            candidate=load(args.candidate);obs=bulletin.validate_observation(candidate,load(args.observation))
            prior=state(c);previous=prior['observations'].get(candidate['id'],{})
            previous_issue=prior['issues'].get(previous.get('runId'),{})
            if previous_issue.get('stage')=='published' and bible.parse(previous_issue['reference'])!=bible.parse(obs['passage']):
                raise ValueError('Published bulletin changed passage; explicit revision required')
            result=make_run(c,obs['passage'],obs['date'],obs['service'],'publish')
            s=state(c);s['observations'][candidate['id']]=dict(contentSha256=candidate['contentSha256'],runId=result['runId'],observation=obs);save(c['root']/'state.json',s)
            save(runpath(c,result['runId'])/'bulletin.json',dict(candidate=candidate,observation=obs))
        elif command=='status':result=load(runpath(c,args.run_id)/'run.json')
        elif command=='claim':
            path=runpath(c,args.run_id);run=load(path/'run.json');lease=run.get('lease')
            if run['stage']=='published':result={'status':'already-published','url':run.get('url')}
            elif lease and lease['expires']>time.time():result={'status':'busy','owner':lease['owner'],'expires':lease['expires']}
            elif lease and not args.resume_expired:result={'status':'interrupted-needs-resume','stage':run['stage']}
            elif run.get('failureCount',0)>=3 and not args.manual_recovery:result={'status':'needs-attention','reason':'Three failed attempts; no automatic retry'}
            elif run.get('lastFailure') and not args.changed_evidence:result={'status':'needs-changed-evidence','failure':run['lastFailure']}
            else:
                if args.manual_recovery:run['failureCount']=0
                if args.changed_evidence:run['attempts'].append(dict(experiment=args.changed_evidence,at=dt.datetime.now(dt.timezone.utc).isoformat()))
                run['lastFailure']=None
                run['lease']=dict(token=secrets.token_hex(16),owner=args.owner,expires=time.time()+21600);save(path/'run.json',run);result={'status':'claimed',**run['lease'],'path':str(path),'stage':run['stage']}
        else:
            path,run=owned(c,args.run_id,args.token)
            if command=='promote':
                run['mode']='publish';save(path/'run.json',run);result={'status':'publish-mode','stage':run['stage']}
            elif command=='passage':
                p=bible.extract(run['reference']);save(path/'passage.json',p);advance(c,path,run,'passage-confirmed');result={'status':'passage-confirmed','file':str(path/'passage.json'),'corrections':p['corrections']}
            elif command=='checkpoint':
                run['attempts'].append(dict(stage=args.stage,evidence=args.evidence,at=dt.datetime.now(dt.timezone.utc).isoformat()));advance(c,path,run,args.stage);result={'status':args.stage}
            elif command=='render':
                m=load(path/'manuscript.json');p=load(path/'passage.json');name=Path(run['relativePath']).name
                if m.get('date')!=run['date']:raise ValueError('Manuscript date differs from issue')
                doc,meta=render.render(m,p,path,run['id'],name);(path/name).write_text(doc,encoding='utf-8',newline='\n');save(path/'render.json',dict(meta,htmlSha256=digest(doc.encode()),file=name));advance(c,path,run,'rendered');result=dict(status='rendered',file=str(path/name),**meta)
                if args.print_proof:
                    (path/'print-proof.html').write_text(render.print_proof(doc),encoding='utf-8',newline='\n')
                    result['printProof']=str(path/'print-proof.html')
            elif command=='validate':
                result=audit_review(path,run);advance(c,path,run,'validated');result['status']='validated'
            elif command=='publish':result=publish(c,path,run)
            elif command=='verify':result=verify_deployment(c,path,run)
            elif command=='release':
                run['lease']=None;save(path/'run.json',run);result={'status':'released','stage':run['stage']}
            elif command=='fail':
                run['attempts'].append(dict(stage=run['stage'],error=args.reason,changedEvidence=args.changed_evidence,at=dt.datetime.now(dt.timezone.utc).isoformat()))
                run['lastFailure']=args.reason;run['failureCount']=run.get('failureCount',0)+1
                run['lease']=None;save(path/'run.json',run);result={'status':'failed-recoverable','stage':run['stage']}
        print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    try:main()
    except Exception as e:
        print(json.dumps({'status':'error','type':type(e).__name__,'message':str(e)},ensure_ascii=False),file=sys.stderr);sys.exit(1)
