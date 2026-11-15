#!/usr/bin/env python3
"""Build annotation instances from the jp-errant-zh M2 file.

One instance = one first-reference edit (annotator id 0 by default), with the
source sentence, that reference's fully corrected sentence, character offsets
for the edit span, and the sampling stratum.

Usage:
    python scripts/10_build_instances.py \
        --m2 data/MuCGEC_dev.m2 \
        --out outputs/instances.jsonl
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import (parse_m2, char_offsets, apply_edits, classify, stratum,
                      dump_jsonl, filter_meta_sentences,
                      is_artifact_instance)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--m2', default='data/MuCGEC_dev.m2')
    ap.add_argument('--out', default='outputs/instances.jsonl')
    ap.add_argument('--ref', type=int, default=0, help='reference/annotator id')
    ap.add_argument('--keep-meta', action='store_true',
                    help='keep sentences whose reference is a meta-comment '
                         '(没有错误 / 无法标注); excluded by default')
    args = ap.parse_args()

    sentences = parse_m2(args.m2)
    if not args.keep_meta:
        sentences, n_meta = filter_meta_sentences(sentences)
        print(f'excluded {n_meta} sentences with meta-comment references '
              f'(没有错误 / 无法标注)')
    rows, strata = [], collections.Counter()
    for s in sentences:
        edits = s.edits_by_ref.get(args.ref, [])
        if not edits:
            continue
        offs = char_offsets(s.tokens)
        src_text = ''.join(s.tokens)
        cor_text = apply_edits(s.tokens, edits)
        for e in edits:
            st = stratum(s.tokens, e.start, e.end, e.label, e.correction)
            strata[st] += 1
            rows.append({
                'id': f's{s.sent_idx:04d}_e{e.edit_idx:02d}_r{args.ref}',
                'sent_idx': s.sent_idx,
                'edit_idx': e.edit_idx,
                'ref_id': args.ref,
                'n_refs': len(s.edits_by_ref),
                'src_text': src_text,
                'cor_text': cor_text,
                'char_start': offs[e.start],
                'char_end': offs[e.end],
                'src_span': src_text[offs[e.start]:offs[e.end]],
                'cor_span': e.correction.replace(' ', ''),
                'tool_label': e.label,
                'tool_op': e.label.split(':')[0],
                'coverage_class': classify(s.tokens, e.start, e.end, e.label, e.correction),
                'stratum': st,
            })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    dump_jsonl(rows, args.out)
    print(f'{len(rows)} instances from {len(sentences)} sentences -> {args.out}')
    for k, v in strata.most_common():
        print(f'  {k:16s} {v:5d}')
    # extraction errors are excluded from every analysis; what remains is the
    # population the two samples are drawn from
    population = collections.Counter(r['stratum'] for r in rows
                                     if not is_artifact_instance(r))
    n_pop = sum(population.values())
    print(f'{len(rows) - n_pop} extraction errors; population without them: '
          f'{n_pop} edits (count and share per stratum)')
    for k, v in population.most_common():
        print(f'  {k:16s} {v:5d}  {v / n_pop:.3f}')


if __name__ == '__main__':
    main()
