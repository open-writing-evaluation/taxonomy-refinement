#!/usr/bin/env python3
"""Build the second coder's copy of the T3 blind-adjudication sheet.

Coder 2 (an expert not involved in the taxonomy's design) adjudicates the
SAME frozen H items (outputs/adjudication/h_ids.json; selection seed 20260717,
untouched here) under the T3 guideline only, per the two-coder protocol
(outputs/adjudication/two_coder_protocol.md). This script writes a
format-identical, blank sheet with an independently shuffled item order:

  outputs/adjudication/h_T3_sheet_c2.xlsx / .csv

With --calibration it additionally writes a 10-item practice sheet drawn
from D_ref (never from H or D_test), for format familiarization only; the
practice labels are not scored and play no role in any analysis:

  outputs/adjudication/h_T3_calibration_10.xlsx

The original coder-1 sheet and h_ids.json are never modified. Note: the
released repository ships coder 2's FILLED first-pass sheet at
h_T3_sheet_c2.xlsx; rerunning this script overwrites it with a blank
copy, so move the filled sheet elsewhere first.

Usage:
    python scripts/75_make_c2_sheet.py [--calibration]
"""
import argparse
import collections
import importlib.util
import json
import os
import random
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from prompting import mark_span

_spec = importlib.util.spec_from_file_location(
    'make_h_sheet', os.path.join(os.path.dirname(__file__),
                                 '70_make_h_sheet.py'))
_mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mk)
SPACES, GOLD_COLS, style = _mk.SPACES, _mk.GOLD_COLS, _mk.style

C2_ORDER_SEED = 20260728  # order only; H selection stays seed 20260717


def build_rows(instances):
    rows = []
    for inst in instances:
        s, e = inst['char_start'], inst['char_end']
        if s == e:
            edit = f'INSERT 「{inst["cor_span"]}」'
        elif not inst['cor_span']:
            edit = f'DELETE 「{inst["src_span"]}」'
        else:
            edit = f'「{inst["src_span"]}」 -> 「{inst["cor_span"]}」'
        rows.append({'id': inst['id'],
                     'source_marked': mark_span(inst['src_text'], s, e),
                     'corrected': inst['cor_text'], 'edit': edit,
                     **{c: '' for c in GOLD_COLS},
                     'gold_alternates': '', 'uncertain': '', 'notes': ''})
    return rows


def write_sheet(rows, base, note):
    df = pd.DataFrame(rows)
    df.to_csv(base + '.csv', index=False, encoding='utf-8-sig')
    df.to_excel(base + '.xlsx', index=False, sheet_name='adjudication',
                engine='openpyxl')
    style(base + '.xlsx', len(rows), 'T3', note)
    print(f'{len(rows)} items -> {base}.xlsx')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config/rounds.yaml')
    ap.add_argument('--calibration', action='store_true')
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))['adjudication']
    outdir = os.path.join('outputs', 'adjudication')

    h = json.load(open(os.path.join(outdir, 'h_ids.json')))
    ids = set(h['ids'])
    pool = {r['id']: r for r in load_jsonl(cfg['source'])
            if not is_artifact_instance(r)}
    missing = ids - set(pool)
    if missing:
        sys.exit(f'h_ids not found in {cfg["source"]}: {sorted(missing)[:5]}')
    chosen = [pool[i] for i in sorted(ids)]
    random.Random(f'{C2_ORDER_SEED}_T3_c2').shuffle(chosen)
    write_sheet(
        build_rows(chosen), os.path.join(outdir, 'h_T3_sheet_c2'),
        'Coder-2 copy (independent item order; selection unchanged). Model '
        'outputs are never shown in this sheet; adjudicate from the written '
        'T3 guideline alone, and discuss no item with anyone until both '
        'coders have finished.')
    print('strata:', dict(collections.Counter(
        r['stratum'] for r in chosen)))

    if args.calibration:
        ref = [r for r in load_jsonl('data/samples/d_ref.jsonl')
               if not is_artifact_instance(r)]
        ref = sorted(ref, key=lambda r: r['id'])
        random.Random(f'{C2_ORDER_SEED}_calibration').shuffle(ref)
        write_sheet(
            build_rows(ref[:10]),
            os.path.join(outdir, 'h_T3_calibration_10'),
            'CALIBRATION ONLY: ten practice items from the analysis sample '
            '(not from H). Use them to learn the sheet format and the T3 '
            'guideline; these labels are not scored and are not used in any '
            'analysis.')


if __name__ == '__main__':
    main()
