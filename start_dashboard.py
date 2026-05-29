import http.server
import socketserver
import webbrowser
import os
import socket
import json
import re
import time
import sys
import subprocess
from datetime import date
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

SATNA_BLOCKS = {'MAJHGAWAN','NAGOD','RAMPUR BAGHELAN','SATNA','UNCHAHARA'}
MAIHAR_BLOCKS = {'AMARPATAN','RAMNAGAR','MAIHAR'}


def find_free_port(start=8097):
    for port in range(start, start + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return 0


def install_playwright_if_needed():
    try:
        import playwright.sync_api  # noqa
        return True, 'Playwright ready'
    except Exception:
        pass
    try:
        print('Installing Playwright. First run can take a few minutes...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'playwright'])
        subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])
        return True, 'Playwright installed'
    except Exception as e:
        return False, f'Could not install Playwright automatically: {e}'



def fill_missing_upyantri_from_panchayat(works):
    from collections import Counter, defaultdict
    def norm(x):
        return re.sub(r'\s+', ' ', str(x or '').strip()).upper()
    bad={'', 'NOT ASSIGNED', 'NA', 'N/A', 'NONE', 'NAN'}
    by_block_gp=defaultdict(Counter); by_gp=defaultdict(Counter); by_block=defaultdict(Counter)
    for w in works:
        u=str(w.get('upyantri') or '').strip()
        if norm(u) not in bad:
            by_block_gp[(norm(w.get('block')), norm(w.get('gp')))][u]+=1
            by_gp[norm(w.get('gp'))][u]+=1
            by_block[norm(w.get('block'))][u]+=1
    for w in works:
        u=str(w.get('upyantri') or '').strip()
        if norm(u) in bad:
            key=(norm(w.get('block')), norm(w.get('gp')))
            if by_block_gp.get(key): u=by_block_gp[key].most_common(1)[0][0]
            elif by_gp.get(norm(w.get('gp'))): u=by_gp[norm(w.get('gp'))].most_common(1)[0][0]
            elif by_block.get(norm(w.get('block'))): u=by_block[norm(w.get('block'))].most_common(1)[0][0]
            else: u='अन्य / Not Mapped'
            w['upyantri']=u
        if not str(w.get('engineer') or '').strip() or str(w.get('engineer')).strip().lower()=='not assigned':
            w['engineer']=w.get('upyantri') or u
    return works

def write_works(works):
    works = fill_missing_upyantri_from_panchayat(works)
    # Keep a rich meta block for dropdowns.
    blocks = sorted({w.get('block','') for w in works if w.get('block')})
    clusters = sorted({w.get('cluster','') for w in works if w.get('cluster')})
    types = sorted({w.get('type','') for w in works if w.get('type')})
    statuses = sorted({w.get('status','') for w in works if w.get('status')})
    upyantris = sorted({w.get('upyantri','') for w in works if w.get('upyantri')})
    meta = {
        'title': 'Satna CFT Jal Ganga Dashboard',
        'source': 'JGSA browser scrape',
        'refreshed_on': date.today().isoformat(),
        'rows': len(works),
        'blocks': blocks,
        'clusters': clusters,
        'types': types,
        'statuses': statuses,
        'engineers': ['Not Assigned'],
        'upyantris': upyantris,
    }
    with open(os.path.join(BASE_DIR, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.DASHBOARD_META = ' + json.dumps(meta, ensure_ascii=False) + ';\n')
        f.write('window.WORKS = ' + json.dumps(works, ensure_ascii=False) + ';\n')


def norm_key(k):
    return re.sub(r'[^a-z0-9\u0900-\u097f]+', '', str(k).lower())


def normalize_record(r, fallback_block=''):
    nk = {norm_key(k): v for k, v in r.items()}
    def get(*keys):
        for k in keys:
            v = nk.get(norm_key(k), None)
            if v not in (None, ''):
                return v
        # contains search fallback
        for kk, vv in nk.items():
            for k in keys:
                if norm_key(k) in kk and vv not in (None, ''):
                    return vv
        return ''
    def num(x):
        if isinstance(x, (int, float)): return float(x)
        try:
            s = str(x).replace(',', '').replace('₹','').replace('Cr','').replace('%','').strip()
            # if crores mentioned, convert to rupees
            mul = 10000000 if 'cr' in str(x).lower() else 1
            return float(re.findall(r'-?\d+(?:\.\d+)?', s)[0]) * mul
        except Exception:
            return 0.0
    block = str(get('block','janpad','ब्लॉक','जनपद') or fallback_block).upper().strip()
    sanctioned = num(get('sanctioned','total sanction','sanction amount','कुलस्वीकृत','स्वीकृत'))
    booked = num(get('booked','total booked','booked amount','expenditure','कुलबुक','बुक'))
    status = str(get('status','स्थिति'))
    completed = str(get('completed','पूर्ण'))
    if not status and completed:
        status = 'Completed' if completed not in ('0','False','false') else 'Ongoing'
    return {
        'district': 'Satna' if block in SATNA_BLOCKS else ('Maihar' if block in MAIHAR_BLOCKS else str(get('district','जिला') or 'Satna')),
        'block': block,
        'cluster': str(get('cluster','क्लस्टर')),
        'upyantri': str(get('upyantri','उपयंत्री','sub engineer','subengineer','se')),
        'gp': str(get('gp','panchayat','gram panchayat','पंचायत','ग्रामपंचायत')),
        'type': str(get('work type','worktype','category','श्रेणी','कार्यप्रकार')),
        'status': status,
        'name': str(get('work name','work','name','कार्यनाम','कार्य')),
        'code': str(get('work code','code','कार्यकोड')),
        'ws': sanctioned,
        'ms': 0,
        'wb': booked,
        'mb': 0,
        'pct': (booked/sanctioned) if sanctioned else num(get('pct','booking pct','progress','percentage'))/100,
        'daily': num(get('delta','daily','daily expense')),
        'engineer': 'Not Assigned'
    }


def score_array(arr):
    if not isinstance(arr, list) or len(arr) < 5 or not all(isinstance(x, dict) for x in arr[:min(5,len(arr))]):
        return 0
    keys = set()
    for item in arr[:20]: keys |= {norm_key(k) for k in item.keys()}
    hits = 0
    important = ['block','janpad','panchayat','gp','work','workcode','worktype','status','sanction','booked','उपयंत्री','पंचायत','कार्य']
    for imp in important:
        if any(norm_key(imp) in k for k in keys): hits += 1
    return hits * len(arr)


def find_best_record_list(obj):
    best = []
    def walk(x):
        nonlocal best
        if isinstance(x, list):
            if score_array(x) > score_array(best):
                best = x
            for i in x[:80]: walk(i)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
    walk(obj)
    return best


def refresh_from_jgsa_browser(district='SATNA', snap_date=None):
    if snap_date is None:
        snap_date = date.today().isoformat()
    ok, msg = install_playwright_if_needed()
    if not ok:
        return False, msg, 0

    from playwright.sync_api import sync_playwright
    url = f'https://jgsa.nregsmp.org/?status=all&district={district}&block=&worktype_id=0&date={snap_date}'
    captured = []
    html = ''
    screenshot = os.path.join(BASE_DIR, 'jgsa_browser_snapshot.png')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        def on_response(response):
            ctype = (response.headers.get('content-type') or '').lower()
            if 'json' in ctype or 'api' in response.url.lower():
                try:
                    data = response.json()
                    captured.append({'url': response.url, 'data': data})
                except Exception:
                    pass
        page.on('response', on_response)
        page.goto(url, wait_until='networkidle', timeout=90000)
        page.wait_for_timeout(5000)
        try:
            # Click/load visible tabs, if available, so their API calls are captured too.
            for text in ['Rankings', 'Work Monitor', 'Overview', 'रैंकिंग', 'कार्य']:
                try:
                    page.get_by_text(text, exact=False).first.click(timeout=1500)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass
        except Exception:
            pass
        html = page.content()
        open(os.path.join(BASE_DIR, 'jgsa_browser_snapshot.html'), 'w', encoding='utf-8').write(html)
        try:
            page.screenshot(path=screenshot, full_page=True)
        except Exception:
            pass
        browser.close()

    best = []
    source_url = ''
    for item in captured:
        arr = find_best_record_list(item['data'])
        if score_array(arr) > score_array(best):
            best = arr
            source_url = item['url']

    # Also inspect inline Next/Vite data in final HTML.
    for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.S|re.I):
        txt = m.group(1).strip()
        if not txt or len(txt) < 50: continue
        for candidate in re.findall(r'(\{.*?\}|\[.*?\])', txt[:200000], re.S):
            try:
                obj = json.loads(candidate)
                arr = find_best_record_list(obj)
                if score_array(arr) > score_array(best): best = arr
            except Exception:
                pass

    if not best or len(best) < 10:
        return False, 'Browser opened JGSA but could not find work-level records. Saved jgsa_browser_snapshot.html/png for checking. The site may only expose summary data.', 0

    fallback_block = ''
    works = [normalize_record(r, fallback_block) for r in best if isinstance(r, dict)]
    works = [w for w in works if any([w.get('block'), w.get('gp'), w.get('name'), w.get('code'), w.get('type')])]
    if len(works) < 10:
        return False, f'Captured {len(best)} rows from browser but mapping did not look like work-level records. Saved snapshots.', len(works)

    write_works(works)
    return True, f'Updated from browser scrape. Source API: {source_url[:120]}', len(works)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/refresh-jgsa','/scrape-jgsa'):
            qs = parse_qs(parsed.query)
            district = (qs.get('district',['SATNA'])[0] or 'SATNA').upper()
            snap_date = qs.get('date',[date.today().isoformat()])[0]
            ok, msg, n = refresh_from_jgsa_browser(district, snap_date)
            payload = json.dumps({'ok': ok, 'message': msg, 'records': n}, ensure_ascii=False).encode('utf-8')
            self.send_response(200 if ok else 500)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers(); self.wfile.write(payload); return
        return super().do_GET()

PORT = find_free_port(8097)
url = f'http://localhost:{PORT}/index.html'
print('Opening Satna CFT Dashboard — browser scrape refresh version:')
print(url)
webbrowser.open(url)

with socketserver.TCPServer(('127.0.0.1', PORT), Handler) as httpd:
    print('Serving folder:', BASE_DIR)
    print('Click 🔄 Refresh JGSA Data in dashboard. First click may install Playwright/Chromium and take a few minutes.')
    print('Keep this window open. Press Ctrl+C to stop.')
    httpd.serve_forever()
