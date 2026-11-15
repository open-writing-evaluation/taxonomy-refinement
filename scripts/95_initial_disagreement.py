#!/usr/bin/env python3
"""Where the models disagree under the initial version (T1), development set.

Prints and saves the numbers reported in the paper's first results
subsection:
  - how concentrated the confusions are (label pairs in T1's own label names);
  - the largest confusions, as a share of all model-pair comparisons;
  - the lexical sub-labels: how often two models that both use a sub-label
    choose the same one, and on how many edits exactly one model uses one;
  - per model, the share of insertions, deletions, and reorderings assigned
    to the structural domain;
  - each model's agreement with itself across two identical runs.

Run after 50_agreement.py (panel and --floor runs) and 55_confusion.py
--no-crosswalk for run r1 on the development set.

Usage:
    python scripts/95_initial_disagreement.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from taxonomy_versions import layer_value

MODELS = ['claude', 'gpt', 'qwen', 'deepseek', 'kimi']
RUN, SAMPLE = 'r1', 'd_ref'
RES = os.path.join('outputs', 'results')
PANEL = '+'.join(MODELS)


def main():
    out = {}
    n_pairs_per_item = len(MODELS) * (len(MODELS) - 1) // 2

    # concentration of confusions, in the version's own label names
    pj = json.load(open(os.path.join(RES, f'{RUN}_confusion.{SAMPLE}.raw', 'pairs.json')))
    pairs = sorted(((c, layer, k) for layer, d in pj['pairs'].items() for k, c in d.items()),
                   reverse=True)
    total = sum(c for c, _, _ in pairs)
    comparisons = pj['n_items'] * n_pairs_per_item
    out['confused_label_pairs'] = len(pairs)
    out['share_of_top7'] = sum(c for c, _, _ in pairs[:7]) / total
    out['top7'] = [{'layer': layer, 'pair': k, 'count': c, 'rate_pct': 100 * c / comparisons}
                   for c, layer, k in pairs[:7]]

    # agreement of the panel on this sample (written by 50_agreement.py)
    agr = json.load(open(os.path.join(RES, f'{RUN}_agreement.{SAMPLE}.{PANEL}.json')))['table']
    out['kappa_by_layer'] = {k: agr[k].get('fleiss') for k in ('screen', 'op', 'dom', 'pos', 'ext', 'comp')}
    out['sublabel_same_choice'] = agr['lexsub']['pairwise']

    inst = [r for r in load_jsonl(f'data/samples/{SAMPLE}.jsonl') if not is_artifact_instance(r)]
    panel = {m: {r['id']: r for r in load_jsonl(f'outputs/annotations/{RUN}/{m}.norm.jsonl')}
             for m in MODELS}

    # edits on which exactly one model uses a lexical sub-label
    out['edits_with_one_sublabel_user'] = sum(
        1 for r in inst
        if sum(layer_value(panel[m][r['id']], 'lexsub') is not None for m in MODELS) == 1)

    # share of M/U/WO edits each model assigns to the structural domain
    share = {}
    for m in MODELS:
        num = den = 0
        for r in inst:
            a = panel[m][r['id']]
            if a['valid'] and a['screen'] is False and a['op'] in ('M', 'U', 'WO'):
                den += 1
                num += a['dom'] in ('SYNT', 'STRUCT')
        share[m] = num / den
    out['structural_share_of_M_U_WO'] = share

    # each model against its own second run (written by 50_agreement.py --floor)
    out['intra_annotator_kappa'] = {
        m: json.load(open(os.path.join(RES, f'{RUN}_agreement.{SAMPLE}.{m}+{m}_rep2.json')))['table']['comp']['fleiss']
        for m in MODELS}

    with open(os.path.join(RES, 'initial_disagreement.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
