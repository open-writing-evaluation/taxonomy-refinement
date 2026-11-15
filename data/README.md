# Data

## Source M2 file (included)

`data/MuCGEC_dev.m2` is the study's source file: the publicly
released MuCGEC development split, with one edit-level annotation block per
sentence, produced by the jp-errant-based Chinese error-annotation system
of Gu et al. (2025). No new learner data were collected. 58 sentences whose
first "reference" is an annotator meta-comment (没有错误 / 无法标注) are
excluded by the instance builder; the pool is 1,079 sentences / 4,545
first-reference edits.

## Canonical samples (committed, immutable)

`data/samples/d_ref.jsonl` (n=300) and `data/samples/d_test.jsonl` (n=200)
are the study's samples. They are reproducible byte-identically from the M2
file:

```bash
python scripts/10_build_instances.py
python scripts/20_sample_datasets.py --instances outputs/instances.jsonl
cmp outputs/samples/d_ref.jsonl  data/samples/d_ref.jsonl
cmp outputs/samples/d_test.jsonl data/samples/d_test.jsonl
```

The draw (seed 20260717, config/sampling.yaml) is a single seeded pass:
d_probe (400, simple random; set aside, not used by any round here) ->
d_ref (stratified from the remainder) -> d_test (stratified from what is
left). Disjointness is asserted by the script.

Three rows per sample are string-identical re-segmentation artifacts of the
extraction tool (`m2_utils.is_artifact_instance`); every analysis script
excludes them by default.
