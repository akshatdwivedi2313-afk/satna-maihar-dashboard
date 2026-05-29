import asyncio, os, re
from io import StringIO
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get('MNREGA_WORK_DETAILS_URL') or 'https://mnregaweb4.dord.gov.in/netnregarep/dynamic_work_details.aspx?page=S&lflag=eng&state_name=MADHYA%20PRADESH&state_code=17&fin_year=2026-2027&source=national&Digest=P9DBmKzRsIjmRYs0jHwB8w'

# User-required sequence:
# For every block, fetch all three statuses separately with Work Start Fin Yr = ALL.
STATUSES = [
    ('Ongoing', ['Ongoing']),
    ('Completed', ['Completed']),
    ('Physically Completed', ['Physically Completed', 'Physical Completed', 'Physically complete', 'Physical']),
]

BLOCKS = [
    ('Amarpatan', ['Amarpatan', 'AMARPATAN']),
    ('Maihar', ['Maihar', 'MAIHAR']),
    ('Majhgawan', ['Majhgawan', 'Majhgawa', 'MAJHGAWAN', 'MAJHGAWA']),
    ('Nagod', ['Nagod', 'NAGOD']),
    ('Rampur Baghelan', ['Rampur Baghelan', 'Rampur Baghelan ', 'RAMPUR BAGHELAN']),
    ('Ramnagar', ['Ramnagar', 'RAMNAGAR']),
    ('Satna', ['Satna', 'SATNA']),
    ('Unchahara', ['Unchahara', 'Uchehra', 'Unchehara', 'UNCHAHARA', 'UCHEHRA']),
]

async def option_texts(select):
    return await select.locator('option').evaluate_all('(opts)=>opts.map(o=>({text:(o.textContent||"").trim(), value:(o.value||"").trim()}))')

async def select_if_present(page, wanted_texts, label=''):
    """Select the first dropdown option matching any wanted text. Exact match first, contains second."""
    sels = page.locator('select')
    count = await sels.count()
    wanted_norm = [str(w).strip().lower() for w in wanted_texts if str(w).strip()]
    # Exact option text/value pass
    for i in range(count):
        sel = sels.nth(i)
        opts = await option_texts(sel)
        for wanted in wanted_norm:
            for o in opts:
                text = str(o['text']).strip().lower()
                val = str(o['value']).strip().lower()
                if wanted == text or wanted == val:
                    await sel.select_option(value=o['value'])
                    await page.wait_for_timeout(900)
                    print(f'    selected {label or wanted_texts[0]} -> {o["text"]}')
                    return True
    # Contains pass
    for i in range(count):
        sel = sels.nth(i)
        opts = await option_texts(sel)
        for wanted in wanted_norm:
            for o in opts:
                text = str(o['text']).strip().lower()
                if wanted and wanted in text:
                    await sel.select_option(value=o['value'])
                    await page.wait_for_timeout(900)
                    print(f'    selected {label or wanted_texts[0]} -> {o["text"]}')
                    return True
    print(f'    could not select {label or wanted_texts}')
    return False

async def set_all_dropdowns_to_all(page):
    """Set all filters to ALL before choosing district/block/status.
    This covers Work Category, Panchayat, Proposed Status, Expenditure filters, Work Start FY etc.
    """
    sels = page.locator('select')
    count = await sels.count()
    for i in range(count):
        sel = sels.nth(i)
        opts = await option_texts(sel)
        for o in opts:
            t = o['text'].strip().lower()
            v = o['value'].strip().lower()
            if t in ('all','--all--','select all','-all-') or v in ('all','0','-1') or t == 'all ':
                try:
                    await sel.select_option(value=o['value'])
                    await page.wait_for_timeout(150)
                except Exception:
                    pass
                break

async def submit(page):
    candidates = [
        "input[type=submit]", "input[value*=Submit]", "input[value*=Show]", "input[value*=View]",
        "button:has-text('Submit')", "button:has-text('Show')", "button:has-text('View')"
    ]
    for css in candidates:
        loc = page.locator(css).first
        try:
            if await loc.count():
                await loc.click(timeout=7000)
                try:
                    await page.wait_for_load_state('networkidle', timeout=90000)
                except Exception:
                    await page.wait_for_timeout(8000)
                return
        except Exception:
            pass
    await page.keyboard.press('Enter')
    try:
        await page.wait_for_load_state('networkidle', timeout=90000)
    except Exception:
        await page.wait_for_timeout(8000)

async def parse_tables(page):
    html = await page.content()
    tables = pd.read_html(StringIO(html))
    useful = []
    for df in tables:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [' '.join([str(x) for x in tup if str(x) != 'nan']).strip() for tup in df.columns]
        cols = [str(c) for c in df.columns]
        joined = ' '.join(cols) + ' ' + ' '.join(map(str, df.head(3).values.ravel()))
        if 'Work Code' in joined and ('Amount Booked' in joined or 'Mandays' in joined or 'Work Name' in joined):
            useful.append(df)
    if not useful:
        return pd.DataFrame()
    return pd.concat(useful, ignore_index=True)

async def fetch_one(page, block_name, block_aliases, status_name, status_aliases):
    print(f'Fetching MNREGA block={block_name} status={status_name}')
    await page.goto(BASE_URL, wait_until='networkidle', timeout=120000)
    await page.wait_for_timeout(3000)

    # 1) Reset everything to ALL (including Work Start Fin Yr = ALL)
    await set_all_dropdowns_to_all(page)

    # 2) District SATNA. Site's SATNA district includes Satna + Maihar blocks.
    await select_if_present(page, ['SATNA'], label='district SATNA')

    # Some sites refresh dependent dropdowns after district. Wait and then set filters to all again,
    # but do this BEFORE block selection so block is not reset.
    await page.wait_for_timeout(1200)
    await set_all_dropdowns_to_all(page)
    await select_if_present(page, ['SATNA'], label='district SATNA')

    # 3) Select block.
    block_ok = await select_if_present(page, block_aliases, label=f'block {block_name}')
    if not block_ok:
        print(f'WARNING: Block not selected: {block_name}. Skipping this block/status.')
        return pd.DataFrame()

    # 4) Keep Panchayat/Category/Proposed/Expenditure/Work Start FY as ALL.
    # Do NOT reset all dropdowns here, otherwise block will be reset.

    # 5) Select Work Status.
    status_ok = await select_if_present(page, status_aliases, label=f'status {status_name}')
    if not status_ok:
        print(f'WARNING: Status not selected: {status_name}; continuing with current page status.')

    # 6) Submit and parse table.
    await submit(page)
    await page.wait_for_timeout(5000)

    safe_block = re.sub(r'[^A-Za-z0-9]+', '_', block_name).strip('_').lower()
    safe_status = re.sub(r'[^A-Za-z0-9]+', '_', status_name).strip('_').lower()
    html = await page.content()
    (ROOT / f'mnrega_last_page_{safe_block}_{safe_status}.html').write_text(html, encoding='utf-8')
    (ROOT / 'mnrega_last_page.html').write_text(html, encoding='utf-8')

    df = await parse_tables(page)
    print(f'  rows detected for {block_name}/{status_name}: {len(df)}')
    if not df.empty:
        df['__fetched_block'] = block_name
        df['__fetched_status'] = status_name
    return df

async def main():
    all_rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.set_default_timeout(90000)
        for block_name, block_aliases in BLOCKS:
            for status_name, status_aliases in STATUSES:
                try:
                    df = await fetch_one(page, block_name, block_aliases, status_name, status_aliases)
                    if not df.empty:
                        all_rows.append(df)
                except Exception as e:
                    print(f'ERROR while fetching {block_name}/{status_name}: {e}')
        await browser.close()

    if not all_rows:
        raise SystemExit('MNREGA table was not detected for any block/status. Check mnrega_last_page_*.html artifacts.')

    out = pd.concat(all_rows, ignore_index=True)
    # De-duplicate repeated rows, preserving block/status tags where possible.
    if 'Work Code' in out.columns:
        out = out.drop_duplicates(subset=['Work Code', '__fetched_block', '__fetched_status'], keep='first')
    out.to_csv(ROOT / 'mnrega_jgsa_financials_raw.csv', index=False, encoding='utf-8-sig')
    out.to_excel(ROOT / 'mnrega_jgsa_financials.xlsx', index=False)
    print('Saved', len(out), 'MNREGA rows from block-wise status-wise fetch')

if __name__ == '__main__':
    asyncio.run(main())
