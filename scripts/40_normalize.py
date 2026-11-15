#!/usr/bin/env python3
"""Normalize and validate raw model annotations, taxonomy-version-aware.

The version is resolved from the run id via config/rounds.yaml (override with
--taxonomy). Writes <model>.norm.jsonl next to each raw file:

  {id, model, valid, screen, olabel, osub, op, dom, pos, ext, ext_code, note}

valid=False rows are protocol errors (counted, excluded from the strict
agreement condition). Out-of-schema label values (e.g. an M:ORTH under T1, an
extension code outside the round's inventory) stay valid=True with a
`nonschema-*` note and are tabulated in the summary - they are annotation
behavior under an underspecified guideline, not protocol failure.

Usage:
    python scripts/40_normalize.py --run-id r1
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, dump_jsonl
from taxonomy_versions import norm_one, version_of_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--taxonomy', default=None,
                    help='override version lookup (T1|T1P|T2|T3)')
    args = ap.parse_args()
    version = args.taxonomy or version_of_run(args.run_id)
    d = os.path.join('outputs', 'annotations', args.run_id)
    nonschema = collections.Counter()
    for path in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
        if path.endswith('.norm.jsonl'):
            continue
        model = os.path.basename(path)[:-6]
        raw_rows = list({r['id']: r for r in load_jsonl(path)}.values())  # last per id
        rows = [dict(norm_one(r, version), model=model) for r in raw_rows]
        out_path = path[:-6] + '.norm.jsonl'
        dump_jsonl(rows, out_path)
        n = len(rows)
        bad = sum(1 for r in rows if not r['valid'])
        mapped = sum(1 for r in rows if r['valid'] and r['note'])
        for r in rows:
            for note in (r['note'] or '').split(';'):
                if note.startswith('nonschema'):
                    nonschema[f'{model}:{note}'] += 1
        print(f'{model:16s} [{version}] n={n:4d} protocol_errors={bad:3d} '
              f'({100*bad/max(n,1):.1f}%) normalized={mapped}')
    if nonschema:
        print('\nout-of-schema label values (kept as annotation behavior):')
        for k, v in nonschema.most_common():
            print(f'  {k:40s} {v}')


if __name__ == '__main__':
    main()
