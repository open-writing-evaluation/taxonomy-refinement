#!/usr/bin/env python3
"""Two-coder agreement and consensus for the T3 blind-adjudication sheets.

Per the two-coder protocol (outputs/adjudication/two_coder_protocol.md):
both coders fill their sheets independently; expert-expert agreement is
computed on the INDEPENDENT first-pass labels (this is the number reported
in the paper); disagreements are then resolved by discussion into a
consensus gold, with the tie rule fixed in advance: if discussion does not
converge, the jointly preferred reading is the primary gold and the other
coder's reading enters gold_alternates (credited by V_set). For items the
coders agree on, gold_alternates is the union of the two coders' alternates.

Step 1 - after both sheets are filled, compute agreement:

    python scripts/80_coder_agreement.py compare \
        --c1 outputs/adjudication/h_T3_sheet.xlsx \
        --c2 outputs/adjudication/h_T3_sheet_c2.xlsx

    -> outputs/adjudication/h_T3_coder_agreement.json / .tex

With --write-worksheet it also exports a blank disagreement worksheet,
outputs/adjudication/h_T3_disagreements.csv (fill consensus_* there). The
released file at that path is the FILLED record of the discussion, so the
flag is off by default and reproducing the paper never overwrites it.

Step 2 - after the discussion, build the consensus sheet (format-identical
to a single-coder sheet, so 85_validity.py consumes it unchanged). The
released consensus was built against coder 2's post-review sheet
(h_T3_sheet_c2_final.xlsx; h_T3_c2_changelog.json records every change
from the first-pass sheet):

    python scripts/80_coder_agreement.py build-consensus \
        --c1 outputs/adjudication/h_T3_sheet.xlsx \
        --c2 outputs/adjudication/h_T3_sheet_c2_final.xlsx \
        --resolutions outputs/adjudication/h_T3_disagreements.csv

    -> outputs/adjudication/h_T3_sheet_consensus.xlsx / .csv

Then:  python scripts/85_validity.py --run-id r3 \
           --sheet outputs/adjudication/h_T3_sheet_consensus.xlsx ...
(and --run-id r2 --crosswalk with the same sheet).

Neither coder's raw sheet is ever modified; both are release artifacts.
"""
import argparse
import collections
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import parse_alternate, FW_TRANS
from taxonomy_versions import serialize

_spec = importlib.util.spec_from_file_location(
    'validity', os.path.join(os.path.dirname(__file__), '85_validity.py'))
_val = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_val)
gold_record, cohen_kappa = _val.gold_record, _val.cohen_kappa

SHEET_COLS = ['id', 'source_marked', 'corrected', 'edit',
              'gold_orthographic', 'gold_orth_label', 'gold_orth_subtype',
              'gold_operation', 'gold_domain', 'gold_pos', 'gold_extension',
              'gold_alternates', 'uncertain', 'notes']
GOLD_FIELDS = SHEET_COLS[4:11]
LAYERS = ('screen', 'olabel', 'op', 'dom', 'pos', 'ext_code')


def read_sheet(path):
    df = (pd.read_excel(path) if path.endswith('.xlsx')
          else pd.read_csv(path, encoding='utf-8-sig'))
    df.columns = [str(c).lstrip('﻿') for c in df.columns]
    filled = df[df['gold_orthographic'].astype(str).str.strip().str.upper()
                .isin(['TRUE', 'FALSE', '1', '0', 'YES', 'NO'])]
    return df, {row['id']: row for _, row in filled.iterrows()}


def layer_val(rec, layer):
    if layer == 'screen':
        return 'ORTH' if rec['screen'] else 'CORE'
    if layer == 'olabel':
        return (f"{rec['olabel']}|{rec['osub']}" if rec['screen'] else None)
    if rec['screen']:
        return None
    return rec.get(layer)


def alternates_of(row):
    cell = str(row.get('gold_alternates', '') or '')
    if cell.lower() == 'nan':
        return []
    cell = cell.translate(FW_TRANS)
    return [a for a in (parse_alternate(p) for p in cell.split(';')
                        if p.strip()) if a]


def union_alternates(row1, row2, primary):
    seen, out = {primary}, []
    for a in alternates_of(row1) + alternates_of(row2):
        if a not in seen:
            seen.add(a)
            out.append(a)
    return ';'.join(out)


def cmd_compare(args):
    _, c1 = read_sheet(args.c1)
    _, c2 = read_sheet(args.c2)
    common = [i for i in c1 if i in c2]
    miss1 = [i for i in c2 if i not in c1]
    miss2 = [i for i in c1 if i not in c2]
    print(f'filled: c1={len(c1)} c2={len(c2)} common={len(common)}'
          + (f'  (unfilled in c1: {len(miss1)}, in c2: {len(miss2)})'
             if miss1 or miss2 else ''))
    g1 = {i: gold_record(c1[i]) for i in common}
    g2 = {i: gold_record(c2[i]) for i in common}
    s1 = {i: serialize(g1[i]) for i in common}
    s2 = {i: serialize(g2[i]) for i in common}

    out = {'n': len(common), 'composite': {}, 'per_layer': {},
           'agree_or_alternate': None}
    a, b = [s1[i] for i in common], [s2[i] for i in common]
    out['composite']['agreement'] = float(np.mean(
        [x == y for x, y in zip(a, b)]))
    out['composite']['kappa'] = float(cohen_kappa(a, b))
    for layer in LAYERS:
        pairs = [(layer_val(g1[i], layer), layer_val(g2[i], layer))
                 for i in common]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        if not pairs:
            continue
        la, lb = zip(*pairs)
        out['per_layer'][layer] = {
            'n': len(pairs),
            'agreement': float(np.mean([x == y for x, y in zip(la, lb)])),
            'kappa': float(cohen_kappa(list(la), list(lb)))}
    lenient = [s1[i] == s2[i]
               or s2[i] in alternates_of(c1[i])
               or s1[i] in alternates_of(c2[i]) for i in common]
    out['agree_or_alternate'] = float(np.mean(lenient))

    base = os.path.join('outputs', 'adjudication', 'h_T3_coder_agreement')
    with open(base + '.json', 'w') as f:
        json.dump(out, f, indent=2)
    with open(base + '.tex', 'w') as f:
        f.write('% auto-generated by 80_coder_agreement.py (first-pass '
                'labels, before consensus)\n')
        f.write(f"{100 * out['composite']['agreement']:.1f}\\% composite "
                f"(Cohen's $\\kappa$ = "
                f"{out['composite']['kappa']:.2f}; $n$ = {out['n']})\n")

    dis = []
    for i in common:
        if s1[i] == s2[i]:
            continue
        r1 = c1[i]
        dis.append({'id': i, 'source_marked': r1['source_marked'],
                    'corrected': r1['corrected'], 'edit': r1['edit'],
                    'c1_label': s1[i], 'c2_label': s2[i],
                    'c1_alternates': str(r1.get('gold_alternates', '') or ''),
                    'c2_alternates': str(c2[i].get('gold_alternates', '') or ''),
                    'c1_notes': str(r1.get('notes', '') or ''),
                    'c2_notes': str(c2[i].get('notes', '') or ''),
                    **{f'consensus_{f}': '' for f in GOLD_FIELDS},
                    'unresolved': '', 'resolution_notes': ''})
    print(json.dumps(out, indent=2))
    dpath = os.path.join('outputs', 'adjudication', 'h_T3_disagreements.csv')
    if args.write_worksheet:
        pd.DataFrame(dis).to_csv(dpath, index=False, encoding='utf-8-sig')
        print(f'{len(dis)} disagreements -> {dpath} (fill consensus_* there, '
              f'then run build-consensus)')
    else:
        print(f'{len(dis)} disagreements (worksheet {dpath} left untouched; '
              f'pass --write-worksheet to export a blank one)')


def cmd_build(args):
    df1, c1 = read_sheet(args.c1)
    _, c2 = read_sheet(args.c2)
    res = pd.read_csv(args.resolutions, encoding='utf-8-sig')
    res.columns = [str(c).lstrip('﻿') for c in res.columns]
    res_by_id = {row['id']: row for _, row in res.iterrows()}

    rows, unresolved_missing = [], []
    for _, sheet_row in df1.iterrows():
        i = sheet_row['id']
        if i not in c1 or i not in c2:
            unresolved_missing.append((i, 'sheet not filled by both coders'))
            continue
        r1, r2 = c1[i], c2[i]
        s1, s2 = serialize(gold_record(r1)), serialize(gold_record(r2))
        out = {'id': i, 'source_marked': r1['source_marked'],
               'corrected': r1['corrected'], 'edit': r1['edit'],
               'uncertain': '', 'notes': ''}
        if s1 == s2:
            for f in GOLD_FIELDS:
                out[f] = '' if str(r1[f]).lower() == 'nan' else r1[f]
            out['gold_alternates'] = union_alternates(r1, r2, s1)
            out['notes'] = 'agreed'
        else:
            rr = res_by_id.get(i)
            if rr is None or str(rr.get('consensus_gold_orthographic', '')
                                 ).strip().upper() not in (
                                     'TRUE', 'FALSE', '1', '0', 'YES', 'NO'):
                unresolved_missing.append((i, 'no consensus recorded'))
                continue
            for f in GOLD_FIELDS:
                v = rr.get(f'consensus_{f}', '')
                out[f] = '' if str(v).lower() == 'nan' else v
            cons = serialize(gold_record(
                {f: out[f] for f in GOLD_FIELDS}))
            alts = union_alternates(r1, r2, cons)
            if str(rr.get('unresolved', '')).strip().lower() == 'yes':
                other = s2 if cons == s1 else s1
                if other != cons and other not in alts.split(';'):
                    alts = ';'.join([a for a in [alts, other] if a])
            out['gold_alternates'] = alts
            out['notes'] = ('consensus (unresolved; second reading in '
                            'alternates)' if str(rr.get('unresolved', '')
                                                 ).strip().lower() == 'yes'
                            else 'consensus')
        rows.append(out)

    if unresolved_missing:
        for i, why in unresolved_missing[:10]:
            print(f'  UNRESOLVED {i}: {why}', file=sys.stderr)
        sys.exit(f'{len(unresolved_missing)} items lack a consensus; '
                 f'fill {args.resolutions} and re-run.')

    df = pd.DataFrame(rows)[SHEET_COLS]
    base = os.path.join('outputs', 'adjudication', 'h_T3_sheet_consensus')
    df.to_csv(base + '.csv', index=False, encoding='utf-8-sig')
    df.to_excel(base + '.xlsx', index=False, sheet_name='adjudication',
                engine='openpyxl')
    n_agree = int((df['notes'] == 'agreed').sum())
    print(f'{len(df)} consensus items -> {base}.xlsx '
          f'({n_agree} agreed, {len(df) - n_agree} discussed)')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('compare')
    p2 = sub.add_parser('build-consensus')
    for p in (p1, p2):
        p.add_argument('--c1', default='outputs/adjudication/h_T3_sheet.xlsx')
        p.add_argument('--c2',
                       default='outputs/adjudication/h_T3_sheet_c2.xlsx')
    p1.add_argument('--write-worksheet', action='store_true',
                    help='export a blank disagreement worksheet (overwrites '
                         'outputs/adjudication/h_T3_disagreements.csv)')
    p2.add_argument('--resolutions',
                    default='outputs/adjudication/h_T3_disagreements.csv')
    args = ap.parse_args()
    (cmd_compare if args.cmd == 'compare' else cmd_build)(args)


if __name__ == '__main__':
    main()
