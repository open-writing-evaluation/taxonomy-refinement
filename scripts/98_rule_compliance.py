#!/usr/bin/env python3
"""How closely the models follow the domain rule once it is stated.

For every version and both samples, pooled over the five models:
  - the share of insertions, deletions, and reorderings (M, U, WO) assigned
    to the structural domain (a judgment under T1, a stated rule from T2);
  - the share of replacements (R) not assigned to the structural domain
    (a judgment under T1 and T2, a stated rule under T3).

Usage:
    python scripts/98_rule_compliance.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance

MODELS = ['claude', 'gpt', 'qwen', 'deepseek', 'kimi']
RUNS = ['r1', 'ctrl', 'r2', 'r3']
SAMPLES = {'d_ref': 'data/samples/d_ref.jsonl', 'd_test': 'data/samples/d_test.jsonl'}
STRUCTURAL = ('SYNT', 'STRUCT')      # the domain was renamed between versions


def main():
    out = {}
    for run in RUNS:
        for sample, path in SAMPLES.items():
            inst = [r for r in load_jsonl(path) if not is_artifact_instance(r)]
            muwo = [0, 0]
            repl = [0, 0]
            for m in MODELS:
                ann = {r['id']: r for r in load_jsonl(f'outputs/annotations/{run}/{m}.norm.jsonl')}
                for r in inst:
                    a = ann[r['id']]
                    if not a['valid'] or a['screen'] is not False:
                        continue
                    if a['op'] in ('M', 'U', 'WO'):
                        muwo[1] += 1
                        muwo[0] += a['dom'] in STRUCTURAL
                    elif a['op'] == 'R':
                        repl[1] += 1
                        repl[0] += a['dom'] not in STRUCTURAL
            out[f'{run}.{sample}'] = {
                'M_U_WO_structural': muwo[0] / muwo[1], 'n_M_U_WO': muwo[1],
                'R_not_structural': repl[0] / repl[1], 'n_R': repl[1]}
            print(f"{run:5s} {sample:7s} M/U/WO structural {100*muwo[0]/muwo[1]:5.1f}% (n={muwo[1]})   "
                  f"R not structural {100*repl[0]/repl[1]:5.1f}% (n={repl[1]})")
    with open(os.path.join('outputs', 'results', 'rule_compliance.json'), 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
