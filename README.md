# DGTR: Disagreement-Guided Taxonomy Refinement

Code, data, and materials for the paper

> Mengyang Qiu, Yang Gu, and Jungyeul Park.
> **LLMs Probe, Experts Decide: Disagreement-Guided Taxonomy Refinement.**
> To appear in *Findings of EACL 2027*.

## What the study does

Annotation projects label text with a fixed set of categories, a
*taxonomy*. When annotators disagree again and again on the same kinds of
items, the cause is often the taxonomy itself: two labels overlap, a rule is
vague, or a distinction is too fine to apply. Finding such defects usually
takes a new round of human annotation after every revision.

DGTR uses several large language models (LLMs) as annotators instead.

1. All models label the same data under the current version of the
   taxonomy.
2. The disagreements that recur are located (which labels compete) and
   diagnosed by experts.
3. The experts decide what to change. Each revision is written into a
   *revision record* with its expected effect before the data are annotated
   again, so the prediction can fail.
4. The next version is annotated in the same way, and the predictions are
   checked.

The paper tests the method in a retrospective case study on a taxonomy of
Chinese learner grammatical errors. Five LLMs labeled the same edits under
three existing versions (T1, T2, T3) and under a control that keeps the
labels and rules of T1 and changes only the wording. Two fixed samples are
used: a development set of 300 edits, which was inspected when the results
were analyzed, and a test set of 200 edits, which was only scored. Two
experts then labeled 150 test-set edits under T3, independently and without
seeing any model output.

## Reproducing the paper's numbers

No API keys are needed. Everything is computed from the committed
annotations and expert sheets, in about five minutes.

```bash
conda env create -f environment.yml && conda activate taxonomy
bash reproduce.sh
```

`reproduce.sh` runs the numbered scripts in order. Each script prints its
numbers and saves them in `outputs/results/`, and the two figures are
redrawn in `figures/`. All resampling uses fixed seeds, so a new run gives
the numbers of the paper.

## Where each table and figure comes from

| In the paper | Script | Result file |
|---|---|---|
| Table 3 and Figure 1, agreement among the five models | `50_agreement.py`, `92_common_space.py` (shared label set) | `<run>_agreement.<sample>.<models>.json`, `common_space.json` |
| Section 4.1, disagreement under the initial version | `55_confusion.py`, `95_initial_disagreement.py` | `<run>_confusion.<sample>.*/pairs.json`, `initial_disagreement.json` |
| Section 4.2, agreement across versions and the four checks | `50_agreement.py`, `90_trajectory.py` (gains, share of rewording), `92_common_space.py`, `94_sensitivity.py`, `98_rule_compliance.py`, `40_normalize.py` | as above, `trajectory.json`, `sensitivity.json`, `rule_compliance.json` |
| Table 4 and Section 4.3, revision outcomes | `97_revision_outcomes.py` | `revision_outcomes.json`, `revision_outcomes.csv` |
| Figures 1 and 2 | `99_figures.py` | `figures/fig_agreement.pdf`, `figures/fig_outcomes.pdf` (top-level `figures/` folder) |
| Table 5 and Section 4.4, expert check | `80_coder_agreement.py`, `85_validity.py` | `outputs/adjudication/h_T3_coder_agreement.json`, `r3_validity_H.json`, `r2_validity_H.json` |
| Table 6, the taxonomy versions | none; it describes the guideline files | `specs/` |
| Table 7, sampling strata | `10_build_instances.py`, `20_sample_datasets.py` (both print the counts) | `outputs/instances.jsonl`, `data/samples/` |
| Table 8, intra-annotator agreement | `50_agreement.py --floor` | `<run>_agreement.<sample>.<model>+<model>_rep2.json` |

`60_linkage.py` and `96_target_ci.py` write further tables (one row per
revision, and two extra intervals). They are run by `reproduce.sh` but
their output is not printed in the paper.

## Names in the paper and in the files

| In the paper | In the files |
|---|---|
| Development set | `d_ref` |
| Test set | `d_test` |
| T1 | run `r1`, guideline `specs/T1_taxonomy.md` |
| T1 reworded, the wording-only control | run `ctrl`, guideline `specs/T1plus_taxonomy.md` |
| T2 | run `r2`, guideline `specs/T2_taxonomy.md` |
| T3 | run `r3`, guideline `specs/T3_taxonomy.md` |
| Claude Sonnet 5, GPT-5.6-Terra, Qwen3.7-Max, DeepSeek-V4-Pro, Kimi-K2.6 | `claude`, `gpt`, `qwen`, `deepseek`, `kimi` |
| Second run of the same model (intra-annotator agreement) | `<model>_rep2`, option `--floor` |
| Revision record | `specs/revision_log_T1_T2.yaml`, `specs/revision_log_T2_T3.yaml` |
| Full label | `comp` |
| Layers: screening, orthographic label, operation, domain, part of speech, extension, lexical sub-label | `screen`, `olabel`, `op`, `dom`, `pos`, `ext`, `lexsub` |
| Domains: content-word lexical, function-word lexical, structural | `LEX-CONT`, `LEX-FUNC`, `STRUCT` (named `SYNT` in T1 and T2) |
| Shared label set | "common space" |
| Diagnosis types: boundary, priority, missing label, broad label, over-fine distinction | `Boundary`, `Precedence`, `MissingLabel`, `BroadLabel`, `FineGrained` |
| Complex edits | "packaging" |
| Expert check | `outputs/adjudication/`; the 150 edits are "H" |
| Expert 1, who led the design of the taxonomy | coder 1, sheet `h_T3_sheet.xlsx` |
| Expert 2, who had no part in the design | coder 2, sheet `h_T3_sheet_c2.xlsx` |

Table 4 numbers the 17 revisions that have a measurable predicted target,
in the order of the revision record:

| Paper | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Record | RL1-01 | RL1-02 | RL2-01 | RL2-02 | RL2-03 | RL2-04 | RL2-05 | RL2-06 | RL2-08 | RL2-09 | RL2-11 | RL2-12 | RL2-13 | RL2-14 | RL2-15 | RL2-16 | RL2-17 |

RL2-07 (a renamed label), RL2-10 (a formatting rule), and RL2-18 (added
examples) have no measurable target.

## What is in the repository

| Folder | Contents |
|---|---|
| `specs/` | The guideline of every version (`T1`, `T1plus`, `T2`, `T3`, each with its `*_output.md` block on the answer format) and the two revision records, with every revision, its reason, and its predicted targets |
| `config/` | The five models (exact model IDs, decoding settings, output-length limits), the versions, and the sampling settings |
| `data/` | The source M2 file (the MuCGEC development split with edit-level annotations) and the two samples (`data/README.md`) |
| `scripts/` | The pipeline, numbered in run order |
| `figures/` | The two figures of the paper, as drawn by `scripts/99_figures.py` |
| `outputs/annotations/` | The raw and normalized labels of every model under every version, including the second runs, with the exact system prompt (`system_prompt.txt`) and model settings of each version |
| `outputs/adjudication/` | The expert check: the instructions and the two-expert protocol, both experts' independent sheets, the second expert's sheet after review with its change log, the worksheet of the 60 disagreements with the consensus label of each, the consensus sheet, and the agreement between the experts |
| `CGEC_taxonomy.pdf` | Supplementary description of the taxonomy |

The repository holds the primary record (data, guidelines, model
annotations, expert sheets), the analysis code, and the two figures.
Other result files are not committed; `reproduce.sh` regenerates them.

The prompts can be rebuilt exactly. The system prompt of each version is
the guideline file followed by its `*_output.md` block, behind a fixed
preamble (`scripts/prompting.py`). The prompt that was used is archived in
`outputs/annotations/<run>/system_prompt.txt`.

## Running the models again (optional, costs money)

`scripts/30_annotate.py` queries the five models (API keys are read from
the environment; see `config/models.yaml`). Two of the models are reasoning
models without sampling controls, so new labels can differ from the
committed ones. The files in `outputs/annotations/` are the data of the
study.

`70_make_h_sheet.py` and `75_make_c2_sheet.py` write blank expert sheets
over the filled ones, and `80_coder_agreement.py compare --write-worksheet`
writes a blank disagreement worksheet over the filled one. Copy the filled
files elsewhere before running any of the three. `reproduce.sh` runs none
of them in that way.

## Notes

- The two experts are authors of the paper. Expert 1 led the design of the
  taxonomy. Expert 2 had no part in it.
- No new sentences were collected. The M2 file is the previously released
  MuCGEC development split with edit-level annotations (`data/README.md`
  gives details and provenance).

## Copyright and license

Copyright © 2026 The Authors. All rights reserved except as granted below.

- Code in `scripts/` and `config/` is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).
- Original documentation, guidelines, annotations, and other research materials are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
- Noncommercial use, modification, and redistribution are permitted with attribution. Commercial use—including commercial use of modified or derivative works—is prohibited without prior written permission from the copyright holders.
- Third-party materials, including MuCGEC data, remain subject to their original licenses and terms. Nothing in this repository relicenses those materials.
