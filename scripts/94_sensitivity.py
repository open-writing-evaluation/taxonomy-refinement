#!/usr/bin/env python3
"""Sentence-overlap check.

The two samples share no edits, but some sentences contribute edits to
both. This script recomputes composite agreement on the sentence-clean
D_test subset: items whose sentence contributes no edit to D_ref.

Writes outputs/results/sensitivity.json.
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl
cs = importlib.import_module('92_common_space')

RUNS = ('r1', 'ctrl', 'r2', 'r3')


def sentence_clean():
    ref_s = {i['sent_idx'] for i in load_jsonl('data/samples/d_ref.jsonl')}
    test = load_jsonl('data/samples/d_test.jsonl')
    semi = {t['id'] for t in test if t['sent_idx'] not in ref_s}
    out = {'n_semi': len(semi)}
    for run in RUNS:
        ids, common, native, _ = cs.build(run, 'data/samples/d_test.jsonl')
        for label, keep in (('full', None), ('semi', semi)):
            use = ids if keep is None else [i for i in ids if i in keep]
            kn, _ = cs.kappa_of(use, native)
            kc, _ = cs.kappa_of(use, common)
            out[f'{run}.{label}'] = {'native': kn, 'common': kc, 'n': len(use)}
    return out


def main():
    out = {'sentence_clean': sentence_clean()}
    for run in RUNS:
        full, semi = (out['sentence_clean'][f'{run}.{k}'] for k in ('full', 'semi'))
        print(f"{run:5s} kappa on all {full['n']} test edits {full['native']:.3f}, "
              f"on the {semi['n']} sentence-clean edits {semi['native']:.3f}")
    with open('outputs/results/sensitivity.json', 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote outputs/results/sensitivity.json')


if __name__ == '__main__':
    main()
