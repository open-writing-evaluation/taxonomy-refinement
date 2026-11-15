#!/usr/bin/env python3
"""Validity V^(r) against the fixed adjudicated set H, per round.

Scores a round's panel annotations against a filled H sheet (the released
gold is the two-coder consensus): r3 natively, r2 with --crosswalk (T2
records mapped into the final space; inventory-gap items score as errors). Reports per-layer per-model accuracy, majority-vote accuracy,
V (mean model accuracy), V_set (alternates credited), and Cohen's kappa
(majority vs. expert) - overall and per stratum. Emits JSON + tex.

Usage:
    python scripts/85_validity.py --run-id r2 --sheet outputs/adjudication/h_T3_sheet_consensus.xlsx --crosswalk
    python scripts/85_validity.py --run-id r3 --sheet outputs/adjudication/h_T3_sheet_consensus.xlsx
"""
import argparse
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, parse_alternate, FW_TRANS
from taxonomy_versions import VERSIONS, crosswalk_record, serialize, version_of_run

LAYERS = ('screen', 'op', 'dom', 'pos', 'ext_code', 'comp')


def gold_record(row):
    orth = str(row['gold_orthographic']).strip().upper() in ('TRUE', '1', 'YES')
    if orth:
        return {'screen': True,
                'olabel': str(row['gold_orth_label']).strip().upper(),
                'osub': str(row['gold_orth_subtype']).strip().lower(),
                'op': None, 'dom': None, 'pos': None, 'ext_code': None}
    ext = str(row['gold_extension']).strip()
    code = 'none' if ext.lower() in ('none', '', 'nan') else ext.split(':')[0].upper()
    return {'screen': False, 'olabel': None, 'osub': None,
            'op': str(row['gold_operation']).strip().upper(),
            'dom': str(row['gold_domain']).strip().upper(),
            'pos': str(row['gold_pos']).strip().upper(),
            'ext_code': code}


def layer_vals(r, layer):
    if layer == 'screen':
        return 'ORTH' if r['screen'] else 'CORE'
    if layer == 'comp':
        return serialize(r)
    return r.get(layer)


def cohen_kappa(a, b):
    cats = sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    M = np.zeros((len(cats), len(cats)))
    for x, y in zip(a, b):
        M[idx[x], idx[y]] += 1
    n = M.sum()
    po = np.trace(M) / n
    pe = (M.sum(0) * M.sum(1)).sum() / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--models', default='claude,gpt,qwen,deepseek,kimi')
    ap.add_argument('--instances', default='data/samples/d_test.jsonl')
    ap.add_argument('--crosswalk', action='store_true',
                    help='map model records into the final label space before '
                         'scoring (use when the run space differs from the '
                         'gold sheet space, e.g. r2 [T2 space] vs the T3 '
                         'gold; items whose gold uses codes unavailable in '
                         'the run inventory then score as errors, which '
                         'measures the validity cost of the missing labels)')
    args = ap.parse_args()

    version = version_of_run(args.run_id)
    models = args.models.split(',')
    panel = {}
    for m in models:
        path = os.path.join('outputs', 'annotations', args.run_id,
                            f'{m}.norm.jsonl')
        rows = load_jsonl(path)
        if args.crosswalk:
            rows = [crosswalk_record(r, version) for r in rows]
        panel[m] = {r['id']: r for r in rows}
    strata = {r['id']: r['stratum'] for r in load_jsonl(args.instances)}

    df = (pd.read_excel(args.sheet) if args.sheet.endswith('.xlsx')
          else pd.read_csv(args.sheet))
    df = df[df['gold_orthographic'].astype(str).str.strip().str.upper()
            .isin(['TRUE', 'FALSE', '1', '0', 'YES', 'NO'])]
    gold, alts = {}, {}
    for _, row in df.iterrows():
        i = row['id']
        gold[i] = gold_record(row)
        cell = str(row.get('gold_alternates', '') or '').translate(FW_TRANS)
        alts[i] = [a for a in
                   (parse_alternate(p) for p in cell.split(';') if p.strip())
                   if a]

    ids = [i for i in gold
           if all(i in panel[m] and panel[m][i]['valid'] for m in models)]
    print(f'H items adjudicated={len(gold)}  scored={len(ids)} '
          f'(run {args.run_id} [{version}])')

    out = {'run': args.run_id, 'taxonomy': version, 'sheet': args.sheet,
           'n': len(ids), 'per_model': {}, 'majority': {}, 'V': {},
           'kappa_majority': {}}
    maj_rec = {}
    for i in ids:
        counts = collections.Counter(serialize(panel[m][i]) for m in models)
        maj_rec[i] = counts.most_common(1)[0][0]
    for layer in LAYERS:
        gvals = {i: layer_vals(gold[i], layer) for i in ids}
        keep = [i for i in ids if gvals[i] not in (None, 'NAN', 'nan')]
        per_model = {}
        accs = []
        for m in models:
            ok = [layer_vals(panel[m][i], layer) == gvals[i] for i in keep
                  if layer_vals(panel[m][i], layer) is not None]
            per_model[m] = float(np.mean(ok)) if ok else None
            if ok:
                accs.append(np.mean(ok))
        out['per_model'][layer] = per_model
        out['V'][layer] = float(np.mean(accs)) if accs else None
        if layer == 'comp':
            mvals = [maj_rec[i] for i in keep]
            gv = [gvals[i] for i in keep]
            out['majority'][layer] = float(np.mean(
                [a == b for a, b in zip(mvals, gv)]))
            out['kappa_majority'][layer] = float(cohen_kappa(mvals, gv))
        else:
            mv, gv = [], []
            for i in keep:
                vals = [layer_vals(panel[m][i], layer) for m in models]
                vals = [v for v in vals if v is not None]
                if not vals:
                    continue
                mv.append(collections.Counter(vals).most_common(1)[0][0])
                gv.append(gvals[i])
            out['majority'][layer] = (float(np.mean(
                [a == b for a, b in zip(mv, gv)])) if mv else None)

    # V_set on the composite (alternates credited)
    vset = []
    for i in ids:
        acc = [serialize(panel[m][i]) == serialize(gold[i]) or
               serialize(panel[m][i]) in alts.get(i, []) for m in models]
        vset.append(np.mean(acc))
    out['V_set_comp'] = float(np.mean(vset)) if vset else None
    out['n_with_alternates'] = sum(bool(alts.get(i)) for i in ids)

    # gold labels that the version of this run does not have (compared in
    # the final label names, so WO:ORTH counts as CO:ORTH)
    orth_ok = {'CO:ORTH' if x == 'WO:ORTH' else x
               for x in VERSIONS[version]['orth_labels']}
    ext_ok = VERSIONS[version]['ext_codes'] | {'none'}
    out['n_gold_outside_label_set'] = sum(
        gold[i]['olabel'] not in orth_ok if gold[i]['screen']
        else gold[i]['ext_code'] not in ext_ok for i in ids)

    # per-stratum composite V
    by_st = collections.defaultdict(list)
    for i in ids:
        acc = np.mean([serialize(panel[m][i]) == serialize(gold[i])
                       for m in models])
        by_st[strata.get(i, '?')].append(acc)
    out['V_comp_by_stratum'] = {st: float(np.mean(v))
                                for st, v in sorted(by_st.items())}

    base = os.path.join('outputs', 'results', f'{args.run_id}_validity_H')
    os.makedirs(os.path.dirname(base), exist_ok=True)
    with open(base + '.json', 'w') as f:
        json.dump(out, f, indent=2)
    with open(base + '.tex', 'w') as f:
        f.write(f'% auto-generated by 85_validity.py ({args.run_id})\n')
        names = {'screen': 'Screening', 'op': 'Operation', 'dom': 'Domain',
                 'pos': 'POS', 'ext_code': 'Extension', 'comp': 'Composite'}
        for layer in LAYERS:
            v = out['V'][layer]
            mj = out['majority'].get(layer)
            f.write(f"{names[layer]} & "
                    f"{'--' if v is None else f'{100*v:.1f}'} & "
                    f"{'--' if mj is None else f'{100*mj:.1f}'} \\\\\n")
        f.write(f"Composite (V\\textsubscript{{set}}) & "
                f"{100*out['V_set_comp']:.1f} & -- \\\\\n")
    print(json.dumps({k: out[k] for k in
                      ('V', 'majority', 'V_set_comp', 'n_with_alternates',
                       'n_gold_outside_label_set')}, indent=2))
    print(f'wrote {base}.json / .tex')


if __name__ == '__main__':
    main()
