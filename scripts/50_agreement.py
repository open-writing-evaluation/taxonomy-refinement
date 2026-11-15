#!/usr/bin/env python3
"""Inter-annotator agreement over the model panel, per layer, per sample.

Layers: screen, olabel, op, dom, pos, ext (code level), comp (exact
composite), plus unanimity.
Metrics: mean pairwise agreement, Fleiss' kappa, Krippendorff's alpha
(nominal), bootstrap 95% CI on composite kappa. Items with any protocol error
are dropped (strict condition; drop count reported). Artifact edits
(character-null / embedded-marker instances) are excluded by default.

Restrict to one sample with --instances (D_ref and D_test are reported
separately).

Usage:
    python scripts/50_agreement.py --run-id r1 --models claude,gpt,qwen,deepseek,kimi \
        --instances data/samples/d_ref.jsonl
    python scripts/50_agreement.py --run-id r1 --models claude,claude_rep2 --floor \
        --instances data/samples/d_ref.jsonl
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

try:
    import krippendorff
except ImportError:
    krippendorff = None

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from taxonomy_versions import layer_value, serialize, version_of_run

RNG = np.random.default_rng(20260717)
LAYERS = ('screen', 'olabel', 'op', 'dom', 'pos', 'ext', 'lexsub', 'comp')


def load_panel(run_id, models):
    panel = {}
    for m in models:
        path = os.path.join('outputs', 'annotations', run_id, f'{m}.norm.jsonl')
        panel[m] = {r['id']: r for r in load_jsonl(path)}
    return panel


def fleiss_kappa(mat):
    mat = np.asarray(mat, dtype=float)
    if mat.shape[1] < 2:
        return float('nan')
    n, _ = mat.shape
    k = mat[0].sum()
    p_cat = mat.sum(axis=0) / (n * k)
    P_i = ((mat ** 2).sum(axis=1) - k) / (k * (k - 1))
    P_bar, P_e = P_i.mean(), (p_cat ** 2).sum()
    return (P_bar - P_e) / (1 - P_e) if P_e < 1 else float('nan')


def kripp_alpha(rows_by_item):
    if krippendorff is None:
        return float('nan')
    cats = sorted({v for vals in rows_by_item for v in vals if v is not None})
    if len(cats) < 2:
        return float('nan')
    idx = {c: i for i, c in enumerate(cats)}
    data = [[(idx[v] if v is not None else np.nan) for v in vals]
            for vals in rows_by_item]
    arr = np.array(data, dtype=float).T
    return krippendorff.alpha(reliability_data=arr,
                              level_of_measurement='nominal')


def pairwise_pct(rows_by_item):
    tot = agree = 0
    for vals in rows_by_item:
        for a, b in itertools.combinations(vals, 2):
            if a is None or b is None:
                continue
            tot += 1
            agree += (a == b)
    return agree / tot if tot else float('nan')


def compute(panel, ids):
    models = sorted(panel)
    table = {}
    for layer in LAYERS:
        rows = []
        for i in ids:
            vals = [layer_value(panel[m][i], layer) for m in models]
            if layer in ('op', 'dom', 'pos', 'ext', 'olabel'):
                if any(v is None for v in vals):
                    continue
            if layer == 'lexsub':
                # partial layer: keep items where >=2 annotators used LEX:*
                if sum(v is not None for v in vals) < 2:
                    continue
            rows.append(vals)
        if not rows:
            table[layer] = dict(n=0)
            continue
        if layer == 'lexsub':
            # incomplete design: pairwise over available pairs; alpha handles
            # missing values; Fleiss undefined
            table[layer] = dict(n=len(rows), pairwise=pairwise_pct(rows),
                                fleiss=float('nan'), alpha=kripp_alpha(rows))
            continue
        cats = sorted({v for vals in rows for v in vals})
        idx = {c: i for i, c in enumerate(cats)}
        mat = np.zeros((len(rows), len(cats)))
        for r_i, vals in enumerate(rows):
            for v in vals:
                mat[r_i, idx[v]] += 1
        table[layer] = dict(n=len(rows), pairwise=pairwise_pct(rows),
                            fleiss=fleiss_kappa(mat), alpha=kripp_alpha(rows))
    unan = sum(len({serialize(panel[m][i]) for m in models}) == 1 for i in ids)
    table['unanimity'] = dict(n=len(ids), rate=unan / len(ids) if ids else float('nan'))
    return table


def bootstrap_ci(panel, ids, n_boot=1000):
    vals = []
    ids = list(ids)
    for _ in range(n_boot):
        sample = [ids[j] for j in RNG.integers(0, len(ids), len(ids))]
        vals.append(compute(panel, sample)['comp']['fleiss'])
    return (float(np.nanpercentile(vals, 2.5)),
            float(np.nanpercentile(vals, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--models', required=True)
    ap.add_argument('--instances', required=True,
                    help='sample file; agreement restricted to its ids')
    ap.add_argument('--taxonomy', default=None)
    ap.add_argument('--floor', action='store_true',
                    help='pairwise-only report (within-model repeat runs)')
    ap.add_argument('--boot', type=int, default=1000)
    ap.add_argument('--keep-null', action='store_true',
                    help='keep artifact edits (default: excluded)')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    version = args.taxonomy or version_of_run(args.run_id)
    models = args.models.split(',')
    panel = load_panel(args.run_id, models)
    inst = load_jsonl(args.instances)
    keep_ids = {r['id'] for r in inst}
    if not args.keep_null:
        null_ids = {r['id'] for r in inst if is_artifact_instance(r)}
        keep_ids -= null_ids
        print(f'excluded {len(null_ids)} artifact edits')
    common = set.intersection(*[set(p) for p in panel.values()]) & keep_ids
    valid_ids = sorted(i for i in common
                       if all(panel[m][i]['valid'] for m in models))
    print(f'items={len(common)}  dropped(protocol error in any model)='
          f'{len(common) - len(valid_ids)}')

    table = compute(panel, valid_ids)
    if args.boot and not args.floor:
        table['comp']['fleiss_ci'] = list(
            bootstrap_ci(panel, valid_ids, args.boot))

    sample = os.path.basename(args.instances).replace('.jsonl', '')
    slug = '+'.join(models)
    out = args.out or os.path.join(
        'outputs', 'results', f'{args.run_id}_agreement.{sample}.{slug}.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({'run': args.run_id, 'taxonomy': version, 'models': models,
                   'sample': sample, 'n_items': len(common),
                   'n_valid': len(valid_ids), 'table': table}, f, indent=2)
    print(json.dumps(table, indent=2, default=float))
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
