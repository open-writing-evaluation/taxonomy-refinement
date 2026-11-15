#!/usr/bin/env python3
"""Sentence-overlap robustness + target-level uncertainty.

(a) The samples are edit-disjoint but not sentence-disjoint. This script
    recomputes the composite trajectory on the sentence-clean D_test
    subset: items whose sentence contributes no edit to D_ref.
(b) Sentence-clustered bootstrap CIs (B=2000) on the headline domain-pair
    confusion deltas across transitions, in the final (crosswalked) space.

Writes outputs/results/sensitivity.json.
"""
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
import importlib
cs = importlib.import_module('92_common_space')

MODELS = ['claude', 'gpt', 'qwen', 'deepseek', 'kimi']
DOM_MAP = {'SYNT': 'STRUCT'}
RNG = np.random.default_rng(20260717)
B = 2000


def sentence_clean():
    ref_s = {i['sent_idx'] for i in load_jsonl('data/samples/d_ref.jsonl')}
    test = load_jsonl('data/samples/d_test.jsonl')
    semi = {t['id'] for t in test if t['sent_idx'] not in ref_s}
    out = {'n_semi': len(semi)}
    for run in ('r1', 'ctrl', 'r2', 'r3'):
        ids, common, native, _ = cs.build(run, 'data/samples/d_test.jsonl')
        for label, keep in (('full', None), ('semi', semi)):
            use = ids if keep is None else [i for i in ids if i in keep]
            kn, _ = cs.kappa_of(use, native)
            kc, _ = cs.kappa_of(use, common)
            out[f'{run}.{label}'] = {'native': kn, 'common': kc, 'n': len(use)}
    return out


def pairmass(run, sample_path, u, v):
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
        doms = [DOM_MAP.get(r['dom'], r['dom']) for r in recs
                if r['screen'] is False and r['dom']]
        per[i] = (sum(1 for a, b in itertools.combinations(doms, 2)
                      if {a, b} == {u, v}), inst[i]['sent_idx'])
    return per


def delta_ci(u, v, sample_path, before, after):
    pb = pairmass(before, sample_path, u, v)
    pa = pairmass(after, sample_path, u, v)
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
    out = {'sentence_clean': sentence_clean(), 'target_ci': {}}
    targets = [('LEX-FUNC', 'STRUCT', 'r1', 'r2'),
               ('LEX-CONT', 'STRUCT', 'r1', 'r2'),
               ('LEX-FUNC', 'STRUCT', 'r2', 'r3'),
               ('LEX-CONT', 'STRUCT', 'r2', 'r3'),
               ('LEX-CONT', 'LEX-FUNC', 'r2', 'r3')]
    for u, v, a, b in targets:
        for s in ('d_ref', 'd_test'):
            key = f'{u}~{v}.{a}->{b}.{s}'
            out['target_ci'][key] = delta_ci(
                u, v, f'data/samples/{s}.jsonl', a, b)
            r = out['target_ci'][key]
            print(f'{key}: {r["before"]}->{r["after"]} CI {r["ci"]}')
    with open('outputs/results/sensitivity.json', 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote outputs/results/sensitivity.json')


if __name__ == '__main__':
    main()
