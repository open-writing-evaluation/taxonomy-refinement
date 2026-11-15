#!/usr/bin/env python3
"""Fixed-common-label-space agreement + paired, sentence-clustered bootstrap CIs.

Motivation: composite agreement under version-native label spaces is not fully
comparable across versions -- removing a code (LEX:*) mechanically removes its
disagreement, adding codes (MOD/CLF) can legitimately lower agreement. This
script therefore evaluates every run in ONE fixed common space c(y):

  ORTH items  -> the atom "ORTH" (orthographic sublabel inventories differ
                 across versions and are excluded from the common composite)
  CORE items  -> CORE|op|dom_c|pos|ext_c with
                 dom_c: SYNT -> STRUCT (logged rename)
                 ext_c: LEX -> none (T1-only), MOD -> none, CLF -> none
                        (T3-only); the 14 shared codes kept

and reports (a) Fleiss' kappa / mean pairwise per run per sample in c(y), and
(b) PAIRED bootstrap CIs on kappa differences between runs, resampling
SENTENCE clusters (sent_idx) with replacement -- instances from one sentence
stay together, and both runs are evaluated on the identical resample so the
CI is on the difference itself.

Usage:
    python scripts/92_common_space.py            # default panel + pairs
"""
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance

MODELS = ['claude', 'gpt', 'qwen', 'deepseek', 'kimi']
RUNS = ['r1', 'ctrl', 'r2', 'r3']
SAMPLES = {'d_ref': 'data/samples/d_ref.jsonl',
           'd_test': 'data/samples/d_test.jsonl'}
PAIRS = [('r1', 'ctrl'), ('r1', 'r2'), ('ctrl', 'r2'), ('r2', 'r3'),
         ('r1', 'r3')]
B = 1000
RNG = np.random.default_rng(20260717)

DOM_MAP = {'SYNT': 'STRUCT'}
EXT_DROP = {'LEX', 'MOD', 'CLF'}


def common_label(r):
    if r['screen']:
        return 'ORTH'
    dom = DOM_MAP.get(r['dom'], r['dom'])
    ext = r['ext_code'] or 'none'
    if ext in EXT_DROP:
        ext = 'none'
    return f"CORE|{r['op']}|{dom}|{r['pos']}|{ext}"


def native_label(r):
    if r['screen']:
        return f"ORTH|{r['olabel']}|{r['osub']}"
    return f"CORE|{r['op']}|{r['dom']}|{r['pos']}|{r['ext_code']}"


def fleiss(mat):
    n, k = mat.shape[0], mat[0].sum()
    pj = mat.sum(0) / (n * k)
    pi = ((mat * mat).sum(1) - k) / (k * (k - 1))
    pbar, pe = pi.mean(), (pj * pj).sum()
    return (pbar - pe) / (1 - pe) if pe < 1 else float('nan')


def pairwise(labels):
    # labels: n x k array of category indices
    n, k = labels.shape
    agree = sum((labels[:, a] == labels[:, b]).mean()
                for a, b in itertools.combinations(range(k), 2))
    return agree / (k * (k - 1) / 2)


def build(run, sample_path):
    inst = {i['id']: i for i in load_jsonl(sample_path)
            if not is_artifact_instance(i)}
    panels = {}
    for m in MODELS:
        path = f'outputs/annotations/{run}/{m}.norm.jsonl'
        panels[m] = {r['id']: r for r in load_jsonl(path)}
    ids = [i for i in inst
           if all(i in panels[m] and panels[m][i]['valid'] for m in MODELS)]
    common = {i: [common_label(panels[m][i]) for m in MODELS] for i in ids}
    native = {i: [native_label(panels[m][i]) for m in MODELS] for i in ids}
    sent = {i: inst[i]['sent_idx'] for i in ids}
    return ids, common, native, sent


def kappa_of(ids, labs):
    cats = sorted({v for i in ids for v in labs[i]})
    idx = {c: j for j, c in enumerate(cats)}
    mat = np.zeros((len(ids), len(cats)))
    li = np.zeros((len(ids), len(MODELS)), dtype=int)
    for r_i, i in enumerate(ids):
        for c_i, v in enumerate(labs[i]):
            mat[r_i, idx[v]] += 1
            li[r_i, c_i] = idx[v]
    return fleiss(mat), pairwise(li)


def paired_ci(ids_a, labs_a, ids_b, labs_b, sent):
    """Paired clustered bootstrap on kappa(b) - kappa(a); runs share items."""
    ids = [i for i in ids_a if i in set(ids_b)]
    clusters = {}
    for i in ids:
        clusters.setdefault(sent[i], []).append(i)
    keys = sorted(clusters)
    deltas = np.empty(B)
    for b in range(B):
        pick = RNG.choice(len(keys), size=len(keys), replace=True)
        boot = [i for p in pick for i in clusters[keys[p]]]
        ka, _ = kappa_of(boot, labs_a)
        kb, _ = kappa_of(boot, labs_b)
        deltas[b] = kb - ka
    return [float(np.quantile(deltas, 0.025)),
            float(np.quantile(deltas, 0.975))]


def main():
    out = {'point': {}, 'delta_ci': {}}
    cache = {}
    for run in RUNS:
        for s, path in SAMPLES.items():
            if not os.path.exists(f'outputs/annotations/{run}'):
                continue
            ids, common, native, sent = build(run, path)
            cache[(run, s)] = (ids, common, native, sent)
            kc, pc = kappa_of(ids, common)
            kn, pn = kappa_of(ids, native)
            out['point'][f'{run}.{s}'] = {
                'n': len(ids),
                'common': {'kappa': kc, 'pairwise': pc},
                'native': {'kappa': kn, 'pairwise': pn}}
            print(f'{run:7} {s:7} n={len(ids):3d}  common k={kc:.3f} '
                  f'pair={pc*100:.1f}  native k={kn:.3f} pair={pn*100:.1f}')
    for a, b in PAIRS:
        for s in SAMPLES:
            if (a, s) not in cache or (b, s) not in cache:
                continue
            ia, ca, na, sent = cache[(a, s)]
            ib, cb, nb, _ = cache[(b, s)]
            key = f'{a}->{b}.{s}'
            out['delta_ci'][key] = {
                'common': paired_ci(ia, ca, ib, cb, sent),
                'native': paired_ci(ia, na, ib, nb, sent)}
            dc = out['delta_ci'][key]
            print(f'{key:18} d-kappa CI common {dc["common"]} '
                  f'native {dc["native"]}')
    os.makedirs('outputs/results', exist_ok=True)
    with open('outputs/results/common_space.json', 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote outputs/results/common_space.json')


if __name__ == '__main__':
    main()
