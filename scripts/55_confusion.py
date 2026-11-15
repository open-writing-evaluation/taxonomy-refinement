#!/usr/bin/env python3
"""Category-level confusion S_uv per layer, per sample, crosswalk-aware.

Counts symmetric pair disagreements across the panel. With --crosswalk
(default ON), T1/T1P records are mapped into the final label space
(SYNT->STRUCT, WO:ORTH->CO:ORTH) so pairs are comparable across rounds.
Raw-space output is available with --no-crosswalk.

Writes per-layer pair CSVs + a machine-readable JSON (read by
95_initial_disagreement.py and 99_figures.py).

Usage:
    python scripts/55_confusion.py --run-id r1 --models claude,gpt,qwen,deepseek,kimi \
        --instances data/samples/d_ref.jsonl
"""
import argparse
import collections
import itertools
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from taxonomy_versions import crosswalk_record, layer_value, version_of_run

LAYERS = ('screen', 'olabel', 'op', 'dom', 'pos', 'ext')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--models', required=True)
    ap.add_argument('--instances', required=True)
    ap.add_argument('--taxonomy', default=None)
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--no-crosswalk', dest='crosswalk', action='store_false')
    ap.add_argument('--keep-null', action='store_true')
    args = ap.parse_args()

    version = args.taxonomy or version_of_run(args.run_id)
    models = args.models.split(',')
    panel = {}
    for m in models:
        path = os.path.join('outputs', 'annotations', args.run_id,
                            f'{m}.norm.jsonl')
        rows = load_jsonl(path)
        if args.crosswalk:
            rows = [crosswalk_record(r, version) for r in rows]
        panel[m] = {r['id']: r for r in rows}

    inst = load_jsonl(args.instances)
    keep_ids = {r['id'] for r in inst}
    if not args.keep_null:
        keep_ids -= {r['id'] for r in inst if is_artifact_instance(r)}
    ids = sorted(set.intersection(*[set(p) for p in panel.values()]) & keep_ids)
    ids = [i for i in ids if all(panel[m][i]['valid'] for m in models)]

    sample = os.path.basename(args.instances).replace('.jsonl', '')
    space = 'final' if args.crosswalk else 'raw'
    outdir = os.path.join('outputs', 'results',
                          f'{args.run_id}_confusion.{sample}.{space}')
    os.makedirs(outdir, exist_ok=True)

    all_pairs = {}
    for layer in LAYERS:
        key = 'ext' if layer == 'ext' else layer
        S = collections.Counter()
        item_pairs = collections.defaultdict(list)   # pair -> example ids
        for i in ids:
            vals = [layer_value(panel[m][i], key) for m in models]
            for a, b in itertools.combinations(vals, 2):
                if a is None or b is None or a == b:
                    continue
                pair = tuple(sorted((a, b)))
                S[pair] += 1
                if len(item_pairs[pair]) < 8:
                    item_pairs[pair].append(i)
        rows = [{'label_u': u, 'label_v': v, 'S_uv': c,
                 'examples': ';'.join(item_pairs[(u, v)])}
                for (u, v), c in S.most_common()]
        pd.DataFrame(rows).to_csv(os.path.join(outdir, f'{layer}_pairs.csv'),
                                  index=False)
        all_pairs[layer] = {f'{u}~{v}': c for (u, v), c in S.items()}
        print(f'\n== {layer}: top confused pairs ({space} space) ==')
        for r in rows[:args.top]:
            print(f"  {r['label_u']:>16s} ~ {r['label_v']:<16s} {r['S_uv']}")

    with open(os.path.join(outdir, 'pairs.json'), 'w') as f:
        json.dump({'run': args.run_id, 'taxonomy': version, 'sample': sample,
                   'space': space, 'n_items': len(ids), 'pairs': all_pairs},
                  f, indent=2)
    print(f'\nwrote {outdir}/')


if __name__ == '__main__':
    main()
