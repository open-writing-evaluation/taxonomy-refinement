#!/usr/bin/env python3
"""Supplementary bootstrap CIs for two registered checks.

(a) Sentence-clustered bootstrap CIs (B=2000) for the RL2-16 registered
    target: extension-layer ARG~none confusion, T2->T3, both samples.
    Same estimator as 94_sensitivity.delta_ci, at the extension layer.
(b) Paired sentence-clustered CI (B=1000, via 92_common_space.paired_ci)
    on the composite kappa delta T1->T3 restricted to the sentence-clean
    D_test subset (items whose sentences contribute no edit to D_ref).

Writes outputs/results/target_ci.json.
"""
import importlib
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
cs = importlib.import_module('92_common_space')

MODELS = cs.MODELS
B = 2000
RNG = np.random.default_rng(20260717)


def pairmass_ext(run, sample_path, u, v):
    inst = {i['id']: i for i in load_jsonl(sample_path)
            if not is_artifact_instance(i)}
    panels = {m: {r['id']: r for r in
                  load_jsonl(f'outputs/annotations/{run}/{m}.norm.jsonl')}
              for m in MODELS}
    per = {}
    for i in inst:
        recs = [panels[m][i] for m in MODELS
                if i in panels[m] and panels[m][i]['valid']]
        if len(recs) < len(MODELS):
            continue
        exts = [r['ext_code'] for r in recs if r['screen'] is False]
        per[i] = (sum(1 for a, b in itertools.combinations(exts, 2)
                      if {a, b} == {u, v}), inst[i]['sent_idx'])
    return per


def delta_ci(u, v, sample_path, before, after):
    pb = pairmass_ext(before, sample_path, u, v)
    pa = pairmass_ext(after, sample_path, u, v)
    ids = [i for i in pb if i in pa]
    clus = {}
    for i in ids:
        clus.setdefault(pb[i][1], []).append(i)
    keys = sorted(clus)
    deltas = np.empty(B)
    for b in range(B):
        pick = RNG.choice(len(keys), size=len(keys), replace=True)
        boot = [i for p in pick for i in clus[keys[p]]]
        deltas[b] = (sum(pa[i][0] for i in boot)
                     - sum(pb[i][0] for i in boot))
    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return {'before': sum(x[0] for x in pb.values()),
            'after': sum(x[0] for x in pa.values()),
            'ci': [float(lo), float(hi)]}


def main():
    out = {}
    for s in ('d_ref', 'd_test'):
        key = f'ARG~none.r2->r3.{s}'
        out[key] = delta_ci('ARG', 'none', f'data/samples/{s}.jsonl',
                            'r2', 'r3')
        print(f'{key}: {out[key]["before"]}->{out[key]["after"]} '
              f'CI {out[key]["ci"]}')

    ref_s = {i['sent_idx'] for i in load_jsonl('data/samples/d_ref.jsonl')}
    test = load_jsonl('data/samples/d_test.jsonl')
    semi = {t['id'] for t in test if t['sent_idx'] not in ref_s}
    ia, ca, na, sent = cs.build('r1', 'data/samples/d_test.jsonl')
    ib, cb, nb, _ = cs.build('r3', 'data/samples/d_test.jsonl')
    ia2 = [i for i in ia if i in semi]
    ib2 = [i for i in ib if i in semi]
    out['clean.r1->r3.d_test'] = {
        'n': len([i for i in ia2 if i in set(ib2)]),
        'native_ci': cs.paired_ci(ia2, na, ib2, nb, sent),
        'common_ci': cs.paired_ci(ia2, ca, ib2, cb, sent)}
    print('clean subset r1->r3:', out['clean.r1->r3.d_test'])

    with open('outputs/results/target_ci.json', 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote outputs/results/target_ci.json')


if __name__ == '__main__':
    main()
