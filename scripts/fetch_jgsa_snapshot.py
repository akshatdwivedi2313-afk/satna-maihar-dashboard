import asyncio, json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
IST = timezone(timedelta(hours=5, minutes=30))

def today_ist():
    return datetime.now(IST).strftime('%Y-%m-%d')

def clean_num(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def parse_cards(text):
    t = clean_num(text)
    cards = {}
    patterns = {
        'total_target_works': r'([\d,]+)\s+TOTAL TARGET WORKS',
        'total_completed': r'([\d,]+)\s+TOTAL COMPLETED',
        'abhiyan_progress': r'([\d,]+)\s+ABHIYAN PROGRESS',
        'total_sanctioned': r'(₹[\d.,]+\s*Cr)\s+TOTAL SANCTIONED',
        'total_booked': r'(₹[\d.,]+\s*Cr)\s+TOTAL BOOKED',
    }
    for k, pat in patterns.items():
        m = re.search(pat, t, re.I)
        if m:
            cards[k] = m.group(1)
    return cards

async def main():
    district = os.environ.get('JGSA_DISTRICT', 'SATNA').upper()
    date = os.environ.get('JGSA_DATE', today_ist())
    url = os.environ.get('JGSA_URL') or f'https://jgsa.nregsmp.org/?status=all&district={district}&block=&worktype_id=0&date={date}'
    print('Opening', url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1800})
        await page.goto(url, wait_until='networkidle', timeout=90000)
        await page.wait_for_timeout(8000)
        # Save HTML/text for debugging and future parsing
        html = await page.content()
        text = await page.locator('body').inner_text(timeout=30000)
        (ROOT/'jgsa_snapshot.html').write_text(html, encoding='utf-8')
        (ROOT/'jgsa_snapshot.txt').write_text(text, encoding='utf-8')
        # Browser generated PDF of the full dashboard page (works even when site's PDF button has no direct URL)
        try:
            await page.pdf(path=str(ROOT/'latest_jgsa.pdf'), format='A4', print_background=True)
        except Exception as e:
            print('PDF print failed:', e)
        await browser.close()
    cards = parse_cards(text)
    summary = {
        'ok': bool(cards),
        'source_url': url,
        'district': district,
        'date': date,
        'updated_at': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
        'cards': cards,
    }
    js = 'window.JGSA_LIVE_SUMMARY = ' + json.dumps(summary, ensure_ascii=False, indent=2) + ';\n'
    (ROOT/'jgsa_live_summary.js').write_text(js, encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not cards:
        raise SystemExit('JGSA page loaded but summary cards were not detected. Check jgsa_snapshot.txt artifact.')

if __name__ == '__main__':
    asyncio.run(main())
