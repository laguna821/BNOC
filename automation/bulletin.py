"""Public board adapter. Discovery is deterministic; image interpretation stays explicit."""
import datetime as dt
import re
from urllib.parse import urljoin
from bible import fetch, digest, plain

ORIGIN='http://www.chmchurch.org'
BOARD=ORIGIN+'/main/sub.html?pageCode=199'
KST=dt.timezone(dt.timedelta(hours=9))

def due(now=None):
    now=now or dt.datetime.now(KST)
    return (now.weekday() in (4,5) and now.hour in range(6,23,2)) or (now.weekday()==6 and now.hour in (6,8))

def target_sunday(now=None):
    now=now or dt.datetime.now(KST)
    return (now+dt.timedelta(days=(6-now.weekday())%7)).date()

def parse_list(html):
    found={}
    # Real board anchors include title in their inner markup.
    for href,content in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',html,re.S|re.I):
        text=plain(content)
        date=re.search(r'(20\d{2})[년월.\-/ ]+(\d{1,2})[월.\-/ ]+(\d{1,2})\s*일?\s*주보',text)
        number=re.search(r'(?:num=|num%3D)(\d+)',href)
        if date and number and 'www199' in href:
            d=dt.date(*map(int,date.groups()))
            if d.weekday()!=6:continue
            n=number[1];url=ORIGIN+f'/main/sub.html?boardID=www199&num={n}&Mode=view'
            found[n]=dict(id=n,date=d.isoformat(),title=text,url=url)
    return sorted(found.values(),key=lambda x:x['date'],reverse=True)

def discover():
    html=fetch(BOARD).decode('utf-8')
    items=parse_list(html)
    if not items:raise ValueError('Board format changed or no dated bulletins found; do not guess')
    return items

def details(item):
    html=fetch(item['url']).decode('utf-8')
    n=item['id']
    images=list(dict.fromkeys(urljoin(ORIGIN,x) for x in re.findall(r'(?:src|href)=["\']([^"\']*/board/www199/'+re.escape(n)+r'_[^"\']+\.(?:jpg|png|jpeg))["\']',html,re.I)))
    if not images:raise ValueError('Bulletin has no recognized images; inspect page')
    # Only attachment identity affects discovery; view counts cannot cause repeated jobs.
    return dict(item,images=images,attachmentSignature=digest(images))

def validate_observation(candidate,obs):
    if obs['date']!=candidate['date']:raise ValueError('Bulletin title/image dates disagree')
    if obs['service']!='sunday-morning-adult':raise ValueError('Unexpected service')
    if not obs.get('passage') or not obs.get('unambiguous') or not obs.get('visuallyConfirmed'):raise ValueError('Ambiguous passage requires user clarification')
    if not obs.get('evidence') or obs.get('imageUrl') not in candidate['images']:raise ValueError('Missing original image evidence')
    if len(set(obs.get('morningPassages',[obs['passage']])))!=1:raise ValueError('Morning services differ')
    return obs
