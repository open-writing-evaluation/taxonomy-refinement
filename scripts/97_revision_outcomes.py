#!/usr/bin/env python3
"""Outcome of every recorded prediction, on both samples.

For each predicted target of each revision in the two revision records:
  - its value before and after the revision, on the development and test
    samples (confusion targets: count and % of all model-pair comparisons;
    item-set targets: observed agreement in % and the number of edits);
  - whether it moved in the predicted direction (confusion falls,
    agreement rises);
  - a 95% bootstrap interval for the change, resampling whole sentences
    (B = 2000). A change is significant when the interval excludes zero.
    Item sets with fewer than MIN_ITEMS edits are not tested.

For each revision: how many of its targets moved as predicted, per sample.
A revision counts as "as predicted" when all of its targets did.

The summary also gives the number of second-step targets that are small on
the development sample (a confusion below 1% of model-pair comparisons, or
a set of fewer than 20 edits), the number of predicted confusions that do
not occur there, and the share of the annotations of modal edits that use
the modality label under T1, T2, and T3.

An item-set target is scored on its first listed metric.

Writes outputs/results/revision_outcomes.json and revision_outcomes.csv.

Usage:
    python scripts/97_revision_outcomes.py
"""
import collections
import csv
import itertools
import json
import os
import sys

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from taxonomy_versions import crosswalk_record, layer_value, version_of_run

MODELS = ['claude', 'deepseek', 'gpt', 'kimi', 'qwen']
N_PAIRS = len(MODELS) * (len(MODELS) - 1) // 2
RECORDS = [('specs/revision_log_T1_T2.yaml', 'r1', 'r2'),
           ('specs/revision_log_T2_T3.yaml', 'r2', 'r3')]
SAMPLES = {'dev': 'data/samples/d_ref.jsonl', 'test': 'data/samples/d_test.jsonl'}
METRIC_LAYER = {'comp_pairwise': 'comp', 'screen_pairwise': 'screen', 'ext_pairwise': 'ext',
                'dom_pairwise': 'dom', 'op_pairwise': 'op', 'pos_pairwise': 'pos',
                'lexsub_pairwise': 'lexsub'}
B = 2000
SEED = 20260717
MIN_ITEMS = 10        # item sets smaller than this are reported but not tested

INST = {s: {r['id']: r for r in load_jsonl(p) if not is_artifact_instance(r)}
        for s, p in SAMPLES.items()}


def load_panel(run, renamed):
    """Normalized labels of one run; `renamed` maps old label names to T3's."""
    version = version_of_run(run)
    panel = {}
    for m in MODELS:
        rows = load_jsonl(f'outputs/annotations/{run}/{m}.norm.jsonl')
        if renamed:
            rows = [crosswalk_record(r, version) for r in rows]
        panel[m] = {r['id']: r for r in rows}
    return panel


PANELS = {(run, renamed): load_panel(run, renamed)
          for run in ('r1', 'r2', 'r3') for renamed in (True, False)}


def valid_ids(run, sample):
    p = PANELS[(run, False)]
    return [i for i in INST[sample] if all(i in p[m] and p[m][i]['valid'] for m in MODELS)]


def confusion_per_item(run, sample, layer, u, v, renamed=True):
    """Number of model pairs that split between labels u and v, per edit."""
    p = PANELS[(run, renamed)]
    out = {}
    for i in valid_ids(run, sample):
        vals = [layer_value(p[m][i], layer) for m in MODELS]
        out[i] = sum(1 for a, b in itertools.combinations(vals, 2)
                     if a is not None and b is not None and {a, b} == {u, v})
    return out


def agreement_per_item(run, sample, layer, select, value):
    """(agreeing pairs, defined pairs) per edit of one stratum or coverage class."""
    p = PANELS[(run, False)]
    out = {}
    for i in valid_ids(run, sample):
        if INST[sample][i].get(select) != value:
            continue
        vals = [layer_value(p[m][i], layer) for m in MODELS]
        defined = [(a, b) for a, b in itertools.combinations(vals, 2)
                   if a is not None and b is not None]
        out[i] = (sum(a == b for a, b in defined), len(defined))
    return out


def modality_label_use(run, sample):
    """% of the annotations of modal edits that use the modality label."""
    p = PANELS[(run, False)]
    ids = [i for i, r in INST[sample].items() if r.get('coverage_class') == 'trigger:MOD']
    used = sum(p[m][i]['screen'] is False and p[m][i]['ext_code'] == 'MOD'
               for m in MODELS for i in ids)
    return 100 * used / (len(ids) * len(MODELS))


def total(xs):
    return float(sum(xs))


def percent(xs):
    den = sum(x[1] for x in xs)
    return 100 * sum(x[0] for x in xs) / den if den else float('nan')


def bootstrap_change(before, after, sample, stat):
    """95% interval of stat(after) - stat(before), resampling sentences."""
    rng = np.random.default_rng(SEED)
    clusters = collections.defaultdict(list)
    for i in sorted(set(before) | set(after)):
        clusters[INST[sample][i]['sent_idx']].append(i)
    keys = sorted(clusters)
    deltas = []
    for _ in range(B):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        ids = [i for k in pick for i in clusters[keys[k]]]
        d = stat([after[i] for i in ids if i in after]) - stat([before[i] for i in ids if i in before])
        if d == d:
            deltas.append(d)
    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return [float(lo), float(hi)]


def score(target, before_run, after_run, sample):
    if target['kind'] == 'pair':
        renamed = target.get('space') != 'raw'
        args = (target['layer'], str(target['u']), str(target['v']), renamed)
        b = confusion_per_item(before_run, sample, *args)
        a = confusion_per_item(after_run, sample, *args)
        res = {'before': total(b.values()), 'after': total(a.values()),
               'before_pct': 100 * total(b.values()) / (len(b) * N_PAIRS),
               'after_pct': 100 * total(a.values()) / (len(a) * N_PAIRS),
               'n': len(b), 'interval': bootstrap_change(b, a, sample, total),
               'removed_by_revision': not renamed}
        change = res['after'] - res['before']
        moved = 'as predicted' if change < 0 else ('no change' if change == 0 else 'against')
    else:
        layer = METRIC_LAYER[target.get('metrics', ['comp_pairwise'])[0]]
        b = agreement_per_item(before_run, sample, layer, target['select'], target['value'])
        a = agreement_per_item(after_run, sample, layer, target['select'], target['value'])
        res = {'before': percent(list(b.values())), 'after': percent(list(a.values())),
               'n': len(b), 'interval': None, 'removed_by_revision': False}
        if res['after'] != res['after']:            # the layer no longer exists
            res['removed_by_revision'] = True
            moved = 'as predicted'
        else:
            if len(b) >= MIN_ITEMS:
                res['interval'] = bootstrap_change(b, a, sample, percent)
            change = res['after'] - res['before']
            moved = 'as predicted' if change > 0 else ('no change' if change == 0 else 'against')
    res['moved'] = moved
    iv = res['interval']
    res['significant'] = bool(iv and (iv[1] < 0 or iv[0] > 0)) and not res['removed_by_revision']
    return res


def target_name(t):
    if t['kind'] == 'pair':
        raw = ' [labels of the earlier version]' if t.get('space') == 'raw' else ''
        return f"confusion {t['u']}~{t['v']} ({t['layer']}){raw}"
    return f"agreement ({METRIC_LAYER[t.get('metrics', ['comp_pairwise'])[0]]}) on {t['select']}={t['value']}"


def main():
    revisions, distinct = [], {}
    for path, before_run, after_run in RECORDS:
        for e in yaml.safe_load(open(path))['entries']:
            targets = []
            for t in e.get('predicted_targets') or []:
                key = (before_run, target_name(t))
                if key not in distinct:
                    distinct[key] = {'step': f'{before_run}->{after_run}', 'target': target_name(t),
                                     'kind': t['kind'],
                                     **{s: score(t, before_run, after_run, s) for s in SAMPLES}}
                targets.append(distinct[key])
            rev = {'id': e['id'], 'title': e['title'], 'diagnosis': e['diagnosis_types'],
                   'changes': e['operations'], 'targets': targets}
            for s in SAMPLES:
                k = sum(t[s]['moved'] == 'as predicted' for t in targets)
                rev[f'{s}_as_predicted'] = k
                rev[f'{s}_outcome'] = (None if not targets else 'as predicted' if k == len(targets)
                                       else 'partly' if k else 'not as predicted')
            revisions.append(rev)

    measurable = [r for r in revisions if r['targets']]
    summary = {'revisions': len(revisions), 'with_measurable_target': len(measurable),
               'distinct_targets': len(distinct)}
    for s in SAMPLES:
        summary[f'{s}_revisions'] = dict(collections.Counter(r[f'{s}_outcome'] for r in measurable))
        summary[f'{s}_targets_moved'] = dict(collections.Counter(t[s]['moved'] for t in distinct.values()))
        summary[f'{s}_targets_significant'] = dict(collections.Counter(
            t[s]['moved'] for t in distinct.values() if t[s]['significant']))

    second = [t for t in distinct.values() if t['step'] == 'r2->r3']
    summary['second_step_targets'] = len(second)
    summary['second_step_targets_small_on_dev'] = sum(
        t['dev']['before_pct'] < 1 if t['kind'] == 'pair' else t['dev']['n'] < 20
        for t in second)
    summary['predicted_confusions_absent_on_dev'] = sum(
        t['kind'] == 'pair' and t['dev']['before'] == 0 and t['dev']['after'] == 0
        for t in distinct.values())
    summary['modality_label_use_pct'] = {
        s: [modality_label_use(run, s) for run in ('r1', 'r2', 'r3')] for s in SAMPLES}

    out_dir = os.path.join('outputs', 'results')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'revision_outcomes.json'), 'w') as f:
        json.dump({'summary': summary, 'revisions': revisions}, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, 'revision_outcomes.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['revision', 'title', 'diagnosis', 'changes', 'target',
                    'dev_before', 'dev_after', 'dev_n', 'dev_moved', 'dev_significant',
                    'test_before', 'test_after', 'test_n', 'test_moved', 'test_significant'])
        for r in measurable:
            for t in r['targets']:
                def cell(d, key):
                    if t['kind'] == 'pair':
                        return f"{d[key]:.0f} ({d[key + '_pct']:.1f}%)"
                    return '' if d[key] != d[key] else f"{d[key]:.1f}%"
                w.writerow([r['id'], r['title'], '+'.join(r['diagnosis']), '+'.join(r['changes']), t['target'],
                            cell(t['dev'], 'before'), cell(t['dev'], 'after'), t['dev']['n'],
                            t['dev']['moved'], t['dev']['significant'],
                            cell(t['test'], 'before'), cell(t['test'], 'after'), t['test']['n'],
                            t['test']['moved'], t['test']['significant']])
    print(json.dumps(summary, indent=1))
    for r in measurable:
        print(f"{r['id']}  dev {r['dev_as_predicted']}/{len(r['targets'])}  "
              f"test {r['test_as_predicted']}/{len(r['targets'])}  {r['title']}")


if __name__ == '__main__':
    main()
