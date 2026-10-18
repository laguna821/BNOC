"""Create inspected-image delivery derivatives; never certify visual quality."""
import copy
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
from bible import digest

def encode(source, target, encoder, quality, lossless):
    if not encoder.get('node') or not encoder.get('sharp'):
        raise ValueError('Configure imageEncoder.node and imageEncoder.sharp in the private config')
    job=dict(input=str(source),output=str(target),quality=quality,lossless=lossless)
    result=subprocess.run([encoder['node'],str(Path(__file__).with_name('encode_webp.cjs')),encoder['sharp']],
                          input=json.dumps(job).encode(),capture_output=True,timeout=120)
    if result.returncode:
        raise ValueError('WebP encoder failed: '+result.stderr.decode('utf-8',errors='replace')[-1500:])
    return json.loads(result.stdout)

def optimize(manuscript, run_dir, encoder, quality=92, lossless=False):
    if not isinstance(quality,int) or not 1<=quality<=100:
        raise ValueError('WebP quality must be an integer from 1 to 100')
    root=Path(run_dir).resolve();updated=copy.deepcopy(manuscript);rows=[]
    for figure in updated.get('figures',[]):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',figure['id']):
            raise ValueError('Invalid figure ID for delivery filename')
        source=(root/figure['file']).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError('Missing or external image source')
        data=source.read_bytes();source_hash=digest(data)
        if source_hash!=figure.get('sha256'):
            raise ValueError('Image changed before optimization')
        policy=figure.get('deliveryCompression','lossless' if figure.get('kind')=='diagram' else 'lossy')
        if policy not in ('keep','lossy','lossless'):raise ValueError('Unknown deliveryCompression policy')
        row=dict(id=figure['id'],source=figure['file'],sourceSha256=source_hash,inputBytes=len(data))
        if source.suffix.lower() not in ('.png','.jpg','.jpeg') or policy=='keep':
            row.update(status='kept',reason='already-webp-or-vector-or-explicit-keep');rows.append(row);continue
        mode=lossless or policy=='lossless'
        folder=root/'images/optimized'
        if not folder.resolve().is_relative_to(root):raise ValueError('External delivery directory')
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/(figure['id']+'-'+source_hash[:12]+('-lossless' if mode else '-q'+str(quality))+'.webp')
        if target.exists():raise ValueError('Delivery candidate already exists; inspect it before retrying')
        info=encode(source,target,encoder,quality,mode)
        if info.get('skipped'):
            row.update(status='kept',reason=info['skipped']);rows.append(row);continue
        output=target.read_bytes()
        if output[:4]!=b'RIFF' or output[8:12]!=b'WEBP':raise ValueError('Encoder did not produce actual WebP')
        if (info.get('width'),info.get('height'))!=(info.get('sourceWidth'),info.get('sourceHeight')):
            raise ValueError('Image dimensions changed during delivery encoding')
        if info.get('sourceHasAlpha') and not info.get('hasAlpha'):
            raise ValueError('Image transparency lost during delivery encoding')
        if len(output)>=len(data):
            target.unlink()  # only this freshly created, unselected derivative
            row.update(status='kept',reason='webp-not-smaller',candidateBytes=len(output));rows.append(row);continue
        output_hash=digest(output);relative=target.relative_to(root).as_posix()
        provenance=figure.setdefault('provenance',{})
        provenance.setdefault('originalSha256',source_hash)
        provenance.setdefault('originalPath',figure['file'])
        provenance['deliveryEncoding']=dict(tool='sharp '+info['sharpVersion'],format='webp',quality=None if mode else quality,
            lossless=mode,effort=4,width=info['width'],height=info['height'],sourceSha256=source_hash,
            sha256=output_hash,inputBytes=len(data),outputBytes=len(output),encodedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        provenance['sourceInspection']=figure.get('inspection',{})
        figure.update(file=relative,sha256=output_hash,
                      inspection=dict(sha256=output_hash,reviewedAt=None,evidence=''))
        row.update(status='needs-visual-inspection',file=relative,sha256=output_hash,outputBytes=len(output),
                   width=info['width'],height=info['height'],lossless=mode)
        rows.append(row)
    changed=sum(x['status']=='needs-visual-inspection' for x in rows)
    return updated,dict(status='needs-visual-inspection' if changed else 'unchanged',changedFigures=changed,
                        images=rows,originalsRetained=True,automaticVisualApproval=False)
