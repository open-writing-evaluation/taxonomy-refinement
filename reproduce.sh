#!/usr/bin/env bash
# Regenerate every number and figure in the paper from the committed
# annotations and expert sheets. No API keys are needed. Takes a few minutes.
#
#   conda env create -f environment.yml && conda activate taxonomy
#   bash reproduce.sh
#
# Each script prints its numbers and saves them in outputs/results/ (the
# agreement between the two experts goes to outputs/adjudication/). The two
# figures of the paper are redrawn in figures/. All resampling uses fixed
# seeds.
set -euo pipefail
cd "$(dirname "$0")"

PANEL=claude,gpt,qwen,deepseek,kimi
SAMPLES="data/samples/d_ref.jsonl data/samples/d_test.jsonl"

# 1. Rebuild the instances and check that the two committed samples are
#    reproduced byte for byte.
python scripts/10_build_instances.py
python scripts/20_sample_datasets.py --instances outputs/instances.jsonl
cmp outputs/samples/d_ref.jsonl  data/samples/d_ref.jsonl
cmp outputs/samples/d_test.jsonl data/samples/d_test.jsonl

# 2. Normalize the labels, then agreement among the five models per version
#    and sample.
for RUN in r1 ctrl r2 r3; do
  python scripts/40_normalize.py --run-id $RUN
  for S in $SAMPLES; do
    python scripts/50_agreement.py --run-id $RUN --models $PANEL --instances $S
  done
done

# 3. Each model against its own second run (initial and final version).
for RUN in r1 r3; do
  for M in claude gpt qwen deepseek kimi; do
    for S in $SAMPLES; do
      python scripts/50_agreement.py --run-id $RUN --models $M,${M}_rep2 --floor --instances $S
    done
  done
done

# 4. Confusion between labels under T1, T2, and T3, in the label names of
#    T3, and under T1 in its own label names.
for RUN in r1 r2 r3; do
  for S in $SAMPLES; do
    python scripts/55_confusion.py --run-id $RUN --models $PANEL --instances $S
  done
done
python scripts/55_confusion.py --run-id r1 --models $PANEL --instances data/samples/d_ref.jsonl --no-crosswalk

# 5. Expert check: agreement between the two experts, then the models
#    against the expert consensus.
python scripts/80_coder_agreement.py compare \
    --c1 outputs/adjudication/h_T3_sheet.xlsx --c2 outputs/adjudication/h_T3_sheet_c2.xlsx
python scripts/85_validity.py --run-id r3 --sheet outputs/adjudication/h_T3_sheet_consensus.xlsx
python scripts/85_validity.py --run-id r2 --sheet outputs/adjudication/h_T3_sheet_consensus.xlsx --crosswalk

# 6. Gains across versions, the shared label set, and the sentence-overlap
#    check.
python scripts/90_trajectory.py --panel $PANEL
python scripts/92_common_space.py
python scripts/94_sensitivity.py

# 7. Disagreement under the initial version, the outcome of every recorded
#    prediction, the domain rule, and the two figures.
python scripts/95_initial_disagreement.py
python scripts/97_revision_outcomes.py
python scripts/98_rule_compliance.py
python scripts/99_figures.py --out figures

echo
echo "Done. Results are in outputs/results/, figures in figures/."
