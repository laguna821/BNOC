"""Install the authored skill and a device-local path reference, with no secrets."""
import argparse,json,os,shutil,sys
from pathlib import Path
from bible import save
from bnoc import config

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--skills-dir',default=str(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'))
    parser.add_argument('--update',action='store_true')
    args=parser.parse_args();c=config(args.config)
    target=Path(args.skills_dir)/'bnoc-publish'
    if target.exists() and not args.update:raise ValueError('Skill exists; inspect it and use --update for an intentional update')
    source=Path(__file__).parent/'skill'
    for f in source.rglob('*'):
        if f.is_file() and f.name!='local-runtime.json':
            dest=target/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    save(target/'references/local-runtime.json',dict(config=str(Path(args.config).resolve()),python=c['python'],cli=str(c['repo']/'automation/bnoc.py'),pythonOptions=['-X','utf8']))
    print(json.dumps({'installed':str(target),'runtime':str(target/'references/local-runtime.json')},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
