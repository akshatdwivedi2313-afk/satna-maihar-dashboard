import json, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / 'data.js'
CSV = ROOT / 'mnrega_jgsa_financials.csv'
XLSX = ROOT / 'mnrega_jgsa_financials.xlsx'


def load_works():
    txt = DATA_JS.read_text(encoding='utf-8')
    m = re.search(r'window\.WORKS\s*=\s*(\[.*\]);?\s*$', txt, re.S)
    if not m:
        raise SystemExit('Could not find window.WORKS in data.js')
    return json.loads(m.group(1))


def read_financials():
    source = None
    if CSV.exists():
        source = CSV
        df = pd.read_csv(CSV)
    elif XLSX.exists():
        source = XLSX
        # MNREGA report exports have two sub-header rows after the main header.
        df = pd.read_excel(XLSX, header=0, skiprows=[1, 2])
    else:
        raise SystemExit('No mnrega_jgsa_financials.csv/xlsx found')
    print(f'Reading financials from {source.name}')
    return df



def is_jgsa_work_name(name):
    """True only for Jal Ganga/JGSA works, not every MNREGA work in the report."""
    t = str(name or '').strip().lower()
    compact = re.sub(r'[^a-z0-9अ-ह]+', '', t)
    return (
        'jgsa' in compact
        or 'jalsa' in compact
        or 'जलगंगा' in compact
        or 'जलसंवर्धन' in compact
        or 'जलसहभागिता' in compact
    )


def fill_missing_upyantri_from_panchayat(works):
    """Assign missing उपयंत्री using same Janpad+Panchayat mapping from already assigned works.
    Falls back to Panchayat-only, then Janpad-only, so Work Not Permissible / other rows do not stay Not Assigned.
    """
    from collections import Counter, defaultdict
    def norm(x):
        return re.sub(r'\s+', ' ', str(x or '').strip()).upper()
    bad = {'', 'NOT ASSIGNED', 'NA', 'N/A', 'NONE', 'NAN'}
    by_block_gp = defaultdict(Counter)
    by_gp = defaultdict(Counter)
    by_block = defaultdict(Counter)
    for w in works:
        u = str(w.get('upyantri') or '').strip()
        if norm(u) not in bad:
            by_block_gp[(norm(w.get('block')), norm(w.get('gp')))][u] += 1
            by_gp[norm(w.get('gp'))][u] += 1
            by_block[norm(w.get('block'))][u] += 1
    changed = 0
    for w in works:
        u = str(w.get('upyantri') or '').strip()
        if norm(u) in bad:
            key = (norm(w.get('block')), norm(w.get('gp')))
            if by_block_gp.get(key):
                u = by_block_gp[key].most_common(1)[0][0]
            elif by_gp.get(norm(w.get('gp'))):
                u = by_gp[norm(w.get('gp'))].most_common(1)[0][0]
            elif by_block.get(norm(w.get('block'))):
                u = by_block[norm(w.get('block'))].most_common(1)[0][0]
            else:
                u = 'अन्य / Not Mapped'
            w['upyantri'] = u
            changed += 1
        if not str(w.get('engineer') or '').strip() or str(w.get('engineer')).strip().lower() == 'not assigned':
            w['engineer'] = w.get('upyantri') or u
    print(f'filled_missing_upyantri_rows: {changed}')
    return works

def col(df, *names):
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        key = n.strip().lower()
        if key in lowered:
            return lowered[key]
    # fuzzy fallback
    for c in df.columns:
        lc = str(c).strip().lower()
        if all(part.lower() in lc for part in names[0].split()[:3]):
            return c
    raise KeyError(f'Could not find column among {names}')



def normalize_work_code(x):
    """Normalize MGNREGA/JGSA work codes for matching across reports.
    Keeps only letters+digits, uppercases, and removes common separators/spaces.
    """
    t = str(x or '').strip().upper()
    t = re.sub(r'\.0$', '', t)
    t = re.sub(r'[^A-Z0-9]', '', t)
    return t


def main():
    works = fill_missing_upyantri_from_panchayat(load_works())
    # IMPORTANT: dashboard itself already contains only JGSA/Jal Ganga works.
    # So match ALL dashboard work codes with MNREGA financial report — do not filter by work-name text.
    jgsa_codes = {normalize_work_code(w.get('code','')) for w in works if normalize_work_code(w.get('code',''))}
    print(f'jgsa_dashboard_work_codes: {len(jgsa_codes)}')
    df = read_financials()
    if 'SNo.' in df.columns:
        df = df[pd.to_numeric(df['SNo.'], errors='coerce').notna()].copy()
    code_col = col(df, 'Work Code')
    wage_col = col(df, 'JGSA Current FY Wage Booked', 'Amount Booked in current Fin Year (in Rs)')
    # In MNREGA exported Excel, the material booked column normally appears as Unnamed: 17.
    material_col = 'JGSA Current FY Material Booked' if 'JGSA Current FY Material Booked' in df.columns else ('Unnamed: 17' if 'Unnamed: 17' in df.columns else col(df, 'Material'))
    mandays_col = col(df, 'JGSA Current FY Mandays', 'Mandays generated')

    df['__norm_work_code'] = df[code_col].map(normalize_work_code)
    df = df[df['__norm_work_code'].isin(jgsa_codes)].copy()  # only dashboard JGSA work codes are counted
    for c in [wage_col, material_col, mandays_col]:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Keep one clear MNREGA status per work-code. If a work appears in more than one fetched
    # report, prefer Physically Completed > Completed > Ongoing. This fixes the earlier
    # case where works found in completed/physical reports were still shown as missing/ongoing.
    def clean_status(x):
        t = str(x or '').strip()
        l = t.lower()
        if 'physical' in l or 'physically' in l:
            return 'Physically Completed'
        if 'complete' in l:
            return 'Completed'
        if 'ongoing' in l or 'on going' in l:
            return 'Ongoing'
        return t or 'Matched'

    status_source_col = '__fetched_status' if '__fetched_status' in df.columns else ('Work Status' if 'Work Status' in df.columns else None)
    if status_source_col:
        df['__mnrega_status_clean'] = df[status_source_col].map(clean_status)
    else:
        df['__mnrega_status_clean'] = 'Matched'

    status_priority = {'Physically Completed': 3, 'Completed': 2, 'Ongoing': 1, 'Matched': 0}
    def best_status(series):
        vals = [clean_status(x) for x in series if str(x or '').strip()]
        if not vals:
            return 'Matched'
        return sorted(vals, key=lambda v: status_priority.get(v, 0), reverse=True)[0]

    grouped = df.groupby('__norm_work_code', as_index=False).agg({
        wage_col:'sum',
        material_col:'sum',
        mandays_col:'sum',
        '__mnrega_status_clean': best_status
    })
    fmap = {
        str(r['__norm_work_code']).strip(): {
            'fy_wb': float(r[wage_col] or 0),
            'fy_mb': float(r[material_col] or 0),
            'fy_mandays': int(r[mandays_col] or 0),
            'mnrega_status': str(r['__mnrega_status_clean'] or 'Matched')
        }
        for _, r in grouped.iterrows()
    }
    matched = 0
    status_updates = {'Ongoing':0, 'Completed':0, 'Physically Completed':0, 'Matched':0}
    for w in works:
        code = normalize_work_code(w.get('code',''))
        f = fmap.get(code, {'fy_wb':0.0,'fy_mb':0.0,'fy_mandays':0,'mnrega_status':'MNREGA Missing'})
        if code in fmap:
            matched += 1
        w['fy_wb'] = round(f['fy_wb'], 2)
        w['fy_mb'] = round(f['fy_mb'], 2)
        w['fy_booked'] = round(f['fy_wb'] + f['fy_mb'], 2)
        w['fy_mandays'] = int(f['fy_mandays'])
        w['mnrega_jgsa_match'] = code in fmap
        w['mnrega_status'] = f['mnrega_status']
        # For display/filtering, use the MNREGA fetched status when matched from the
        # Completed or Physically Completed reports. Do not force unmatched works to completed.
        if code in fmap and f['mnrega_status'] in ('Completed', 'Physically Completed', 'Ongoing'):
            w['original_status'] = w.get('status','')
            w['status'] = f['mnrega_status']
            status_updates[f['mnrega_status']] = status_updates.get(f['mnrega_status'],0)+1

    DATA_JS.write_text('window.WORKS = ' + json.dumps(works, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    # Save the JGSA-only matched financial sheet for checking/debugging.
    keep_cols = [c for c in [code_col, '__norm_work_code', 'District Name', 'Block Name', 'Panchayat Name', 'Work Status', 'Work Name', '__fetched_status', wage_col, material_col, mandays_col] if c in df.columns]
    df[keep_cols].rename(columns={wage_col:'JGSA Current FY Wage Booked', material_col:'JGSA Current FY Material Booked', mandays_col:'JGSA Current FY Mandays'}).to_csv(CSV, index=False, encoding='utf-8-sig')
    print(json.dumps({
        'matched_jgsa_work_codes': matched,
        'status_updates_from_mnrega': status_updates,
        'fy_wage_booked': round(sum(w.get('fy_wb',0) for w in works),2),
        'fy_material_booked': round(sum(w.get('fy_mb',0) for w in works),2),
        'fy_mandays': int(sum(w.get('fy_mandays',0) for w in works)),
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
