#!/usr/bin/env python3
"""Gains in agreement on the composite label across versions.

Reads the agreement JSONs written by 50_agreement.py for the panel runs
(r1, ctrl, r2, r3) on d_ref and d_test. Reports, per sample, Fleiss' kappa
of each run and the gains: the first step (r1 -> r2), both steps
(r1 -> r3), rewording alone (r1 -> ctrl), and the share of the first-step
gain that rewording alone reaches.

Writes outputs/results/trajectory.json.

Usage:
    python scripts/90_trajectory.py --panel claude,gpt,qwen,deepseek,kimi
"""
import argparse
import json
import os

RUNS = ['r1', 'ctrl', 'r2', 'r3']
SAMPLES = ['d_ref', 'd_test']
RES = os.path.join('outputs', 'results')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', default='claude,gpt,qwen,deepseek,kimi')
    args = ap.parse_args()
    slug = '+'.join(args.panel.split(','))

    comp = {}
    for run in RUNS:
        for s in SAMPLES:
            path = os.path.join(RES, f'{run}_agreement.{s}.{slug}.json')
            if not os.path.exists(path):
                raise SystemExit(f'{path} not found - run 50_agreement.py first')
            comp[(run, s)] = json.load(open(path))['table']['comp']

    gains = {}
    for s in SAMPLES:
        k = {run: comp[(run, s)]['fleiss'] for run in RUNS}
        gains[s] = {'first_step': k['r2'] - k['r1'],
                    'both_steps': k['r3'] - k['r1'],
                    'rewording_alone': k['ctrl'] - k['r1'],
                    'rewording_share_of_first_step':
                        (k['ctrl'] - k['r1']) / (k['r2'] - k['r1'])}

    with open(os.path.join(RES, 'trajectory.json'), 'w') as f:
        json.dump({'kappa': {f'{run}.{s}': comp[(run, s)]['fleiss']
                             for run in RUNS for s in SAMPLES},
                   'kappa_gains': gains}, f, indent=2)
    for (run, s), t in sorted(comp.items()):
        print(f"  {run:5s} {s:7s} comp pairwise={100*t['pairwise']:.1f}% "
              f"kappa={t['fleiss']:.3f} (n={t['n']})")
    for s, g in gains.items():
        print(f"  {s:7s} kappa gain: first step {g['first_step']:.3f}, "
              f"both steps {g['both_steps']:.3f}, rewording alone "
              f"{g['rewording_alone']:.3f} "
              f"({100 * g['rewording_share_of_first_step']:.0f}% of the first step)")
    print('wrote outputs/results/trajectory.json')


if __name__ == '__main__':
    main()
