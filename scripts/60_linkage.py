#!/usr/bin/env python3
"""Revision-linkage analysis: did each logged revision shrink its predicted
confusion target?

For every entry of a revision log, evaluates its predicted targets on the
before-round and after-round outputs, on D_ref AND D_test:

  pair targets    S_uv in the crosswalked (final) label space, from the
                  pairs.json files written by 55_confusion.py, reported as
                  count and rate per item-pair (robust to differing Ns).
  itemset targets pairwise agreement metrics recomputed on the instance
                  subset (stratum or coverage_class), from the .norm files.

Emits CSV + a tex fragment (one row per revision) for the paper's
revision-linkage table.

Usage:
    python scripts/60_linkage.py --log specs/revision_log_T1_T2.yaml \
        --before r1 --after r2 --models claude,gpt,qwen,deepseek,kimi
    python scripts/60_linkage.py --log specs/revision_log_T2_T3.yaml \
        --before r2 --after r3 --models claude,gpt,qwen,deepseek,kimi
"""
import argparse
import itertools
import json
import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from taxonomy_versions import crosswalk_record, layer_value, version_of_run

SAMPLES = {'d_ref': 'data/samples/d_ref.jsonl',
           'd_test': 'data/samples/d_test.jsonl'}
METRIC_LAYER = {'comp_pairwise': 'comp', 'screen_pairwise': 'screen',
                'ext_pairwise': 'ext', 'dom_pairwise': 'dom',
                'op_pairwise': 'op', 'pos_pairwise': 'pos',
                'lexsub_pairwise': 'lexsub'}


def load_pairs(run, sample, space='final'):
    path = os.path.join('outputs', 'results',
                        f'{run}_confusion.{sample}.{space}', 'pairs.json')
    if not os.path.exists(path):
        raise SystemExit(f'missing {path} - run 55_confusion.py for '
                         f'{run}/{sample}' +
                         (' with --no-crosswalk' if space == 'raw' else ''))
    return json.load(open(path))


def load_panel(run, models):
    # RAW (native-space) records: within-round pairwise agreement is
    # unaffected by renames, and the lexsub metric needs the LEX codes that
    # the crosswalk removes. Pair targets use the precomputed crosswalked
    # pairs.json instead.
    panel = {}
    for m in models:
        path = os.path.join('outputs', 'annotations', run, f'{m}.norm.jsonl')
        panel[m] = {r['id']: r for r in load_jsonl(path)}
    return panel


def subset_ids(sample_rows, select, value, panel, models):
    ids = []
    for r in sample_rows:
        if is_artifact_instance(r):
            continue
        if select == 'stratum' and r.get('stratum') != value:
            continue
        if select == 'coverage_class' and r.get('coverage_class') != value:
            continue
        i = r['id']
        if all(i in panel[m] and panel[m][i]['valid'] for m in models):
            ids.append(i)
    return ids


def pairwise_on(panel, models, ids, layer):
    tot = agree = n_def = 0
    for i in ids:
        vals = [layer_value(panel[m][i], layer) for m in models]
        if any(v is not None for v in vals):
            n_def += 1
        for a, b in itertools.combinations(vals, 2):
            if a is None or b is None:
                continue
            tot += 1
            agree += (a == b)
    n = n_def if layer == 'lexsub' else len(ids)
    return (agree / tot if tot else None), n


def fmt(x, pct=False):
    if x is None:
        return '--'
    return f'{100*x:.1f}' if pct else f'{x}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log', required=True)
    ap.add_argument('--before', required=True)
    ap.add_argument('--after', required=True)
    ap.add_argument('--models', required=True)
    args = ap.parse_args()

    models = sorted(args.models.split(','))
    npairs = len(models) * (len(models) - 1) // 2
    log = yaml.safe_load(open(args.log))
    panels = {run: load_panel(run, models) for run in (args.before, args.after)}
    samples = {s: load_jsonl(p) for s, p in SAMPLES.items()}
    spaces_needed = {'final'}
    for e in log['entries']:
        for t in (e.get('predicted_targets') or []):
            if t.get('kind') == 'pair' and t.get('space') == 'raw':
                spaces_needed.add('raw')
    pairs_json = {(run, s, sp): load_pairs(run, s, sp)
                  for run in (args.before, args.after) for s in SAMPLES
                  for sp in spaces_needed}

    rows = []
    for e in log['entries']:
        targets = e.get('predicted_targets') or []
        if not targets:
            rows.append({'revision': e['id'], 'title': e['title'],
                         'types': '+'.join(e['diagnosis_types']),
                         'ops': '+'.join(e['operations']),
                         'target': '(no measurable prediction)',
                         'ref_before': '--', 'ref_after': '--',
                         'test_before': '--', 'test_after': '--'})
            continue
        for t in targets:
            row = {'revision': e['id'], 'title': e['title'],
                   'types': '+'.join(e['diagnosis_types']),
                   'ops': '+'.join(e['operations'])}
            if t['kind'] == 'pair':
                key = '~'.join(sorted((str(t['u']), str(t['v']))))
                sp = t.get('space', 'final')
                row['target'] = f"S({t['layer']}: {t['u']}~{t['v']})" + \
                    (' [raw]' if sp == 'raw' else '')
                for s, col in (('d_ref', 'ref'), ('d_test', 'test')):
                    for run, when in ((args.before, 'before'),
                                      (args.after, 'after')):
                        pj = pairs_json[(run, s, sp)]
                        cnt = pj['pairs'].get(
                            'ext' if t['layer'] == 'ext' else t['layer'],
                            {}).get(key, 0)
                        n = pj['n_items']
                        rate = 100 * cnt / (n * npairs) if n else 0.0
                        row[f'{col}_{when}'] = f'{cnt} ({rate:.1f})'
            elif t['kind'] == 'itemset':
                metrics = t.get('metrics', ['comp_pairwise'])
                m0 = metrics[0]
                layer = METRIC_LAYER[m0]
                row['target'] = (f"{m0} on {t['select']}={t['value']}")
                for s, col in (('d_ref', 'ref'), ('d_test', 'test')):
                    for run, when in ((args.before, 'before'),
                                      (args.after, 'after')):
                        ids = subset_ids(samples[s], t['select'], t['value'],
                                         panels[run], models)
                        val, n = pairwise_on(panels[run], models, ids, layer)
                        row[f'{col}_{when}'] = (
                            f'{100*val:.1f} (n={n})' if val is not None
                            else f'-- (n={n})')
            rows.append(row)

    outdir = os.path.join('outputs', 'results')
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir,
                        f"linkage_{log['log']}_{args.before}_to_{args.after}")
    df = pd.DataFrame(rows)
    df.to_csv(base + '.csv', index=False)
    with open(base + '.tex', 'w') as f:
        f.write('% auto-generated by 60_linkage.py\n')
        f.write('% revision & diagnosis & operations & target & '
                'ref before -> after & test before -> after \\\\\n')
        for r in rows:
            f.write(f"{r['revision']} & {r['types']} & {r['ops']} & "
                    f"{r['target']} & {r['ref_before']} $\\to$ {r['ref_after']} & "
                    f"{r['test_before']} $\\to$ {r['test_after']} \\\\\n")
    print(df.to_string(index=False, max_colwidth=44))
    print(f'wrote {base}.csv / .tex')


if __name__ == '__main__':
    main()
