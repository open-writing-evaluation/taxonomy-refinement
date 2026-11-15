#!/usr/bin/env python3
"""Draw the three disjoint samples with a fixed seed (provenance script).

  d_probe (n=400): simple random, natural distribution -> drawn first and
                   set aside (not used by any round here)
  d_ref   (n=300): stratified from the remainder -> refinement rounds
  d_test  (n=200): stratified from the remainder -> frozen held-out set

The committed files in data/samples/ are canonical and immutable; this
script reproduces them byte-identically from the M2-derived instances
(verify with cmp). The draw order (d_probe, then d_ref, then d_test) is
part of the seeded sequence; do not reorder.

Usage:
    python scripts/10_build_instances.py
    python scripts/20_sample_datasets.py --instances outputs/instances.jsonl
    cmp outputs/samples/d_ref.jsonl data/samples/d_ref.jsonl
    cmp outputs/samples/d_test.jsonl data/samples/d_test.jsonl
"""
import argparse
import collections
import os
import random
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, dump_jsonl


def stratified(pool, allocation, n_target, rng):
    by_stratum = collections.defaultdict(list)
    for r in pool:
        by_stratum[r['stratum']].append(r)
    for v in by_stratum.values():
        rng.shuffle(v)
    chosen = []
    # special allocations first (tiny wo_co class must never be truncated away)
    for st, want in allocation.items():
        if want == 'all_60':
            avail = by_stratum.get(st, [])
            k = max(1, round(len(avail) * 0.6)) if avail else 0
            chosen += avail[:k]
            by_stratum[st] = avail[k:]
        elif want == 'all_rest':
            chosen += by_stratum.get(st, [])
            by_stratum[st] = []
    # numeric allocations, capped so the target is never exceeded
    for st, want in allocation.items():
        if isinstance(want, int):
            room = n_target - len(chosen)
            take = by_stratum.get(st, [])[:min(want, room)]
            chosen += take
            by_stratum[st] = by_stratum.get(st, [])[len(take):]
    # rebalance any deficit from residual_mixed, then residual_open
    for filler in ('residual_mixed', 'residual_open'):
        while len(chosen) < n_target and by_stratum.get(filler):
            chosen.append(by_stratum[filler].pop())
    assert len(chosen) == n_target, f'could not fill sample ({len(chosen)}/{n_target})'
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instances', default='outputs/instances.jsonl')
    ap.add_argument('--config', default='config/sampling.yaml')
    ap.add_argument('--outdir', default='outputs/samples')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    rng = random.Random(cfg['seed'])
    rows = load_jsonl(args.instances)

    # 1. d_probe: simple random, natural distribution (reserved; drawn first
    #    so d_ref/d_test come from the remainder - disjointness by construction)
    ids = list(range(len(rows)))
    rng.shuffle(ids)
    probe_idx = set(ids[:cfg['d_probe']['n']])
    d_probe = [rows[i] for i in sorted(probe_idx)]
    remainder = [rows[i] for i in range(len(rows)) if i not in probe_idx]

    # 2. D_ref stratified from remainder
    d_ref = stratified(remainder, cfg['d_ref']['allocation'], cfg['d_ref']['n'], rng)
    ref_ids = {r['id'] for r in d_ref}
    remainder2 = [r for r in remainder if r['id'] not in ref_ids]

    # 3. D_test stratified from what is left
    d_test = stratified(remainder2, cfg['d_test']['allocation'], cfg['d_test']['n'], rng)

    os.makedirs(args.outdir, exist_ok=True)
    for name, data in (('d_probe', d_probe), ('d_ref', d_ref), ('d_test', d_test)):
        dump_jsonl(data, os.path.join(args.outdir, f'{name}.jsonl'))
        dist = collections.Counter(r['stratum'] for r in data)
        print(f'{name}: n={len(data)}  ' + '  '.join(f'{k}={v}' for k, v in sorted(dist.items())))

    # disjointness guarantee
    all_ids = [r['id'] for r in d_probe] + [r['id'] for r in d_ref] + [r['id'] for r in d_test]
    assert len(all_ids) == len(set(all_ids)), 'samples are not disjoint!'
    print('disjointness check passed.')


if __name__ == '__main__':
    main()
