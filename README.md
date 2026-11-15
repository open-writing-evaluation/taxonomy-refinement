# DGTR: Disagreement-Guided Taxonomy Refinement

Code, data, and materials for

> Mengyang Qiu, Yang Gu, and Jungyeul Park.
> **LLMs Probe, Experts Decide: Disagreement-Guided Taxonomy Refinement.**
> To appear in *Findings of EACL 2027*.

Five LLMs label the same edits under successive versions of a taxonomy.
Their recurring disagreements show where the taxonomy needs work. Experts
decide what to change, and each revision is recorded with a prediction that
the next annotation can confirm or refute. The paper tests the method on a
taxonomy of Chinese learner grammatical errors: three versions (T1, T2, T3)
and a wording-only control, a development set of 300 edits, a test set of
200, and an expert check on 150 test-set edits.

## Reproducing the paper

```bash
conda env create -f environment.yml && conda activate taxonomy
bash reproduce.sh
```

This takes about five minutes and needs no API keys. Everything is computed
from the committed annotations and expert sheets, with fixed seeds. Each
script prints its numbers and saves them in `outputs/results/` (not
committed). The two figures are redrawn in `figures/`.

| In the paper | Script |
|---|---|
| Table 3 and Figure 1, agreement among the models | `50_agreement.py`, `92_common_space.py` |
| Section 4.1, disagreement under T1 | `55_confusion.py`, `95_initial_disagreement.py` |
| Section 4.2, agreement across versions and the checks | `50_agreement.py`, `90_trajectory.py`, `92_common_space.py`, `94_sensitivity.py`, `98_rule_compliance.py`, `40_normalize.py` |
| Table 4 and Section 4.3, revision outcomes | `97_revision_outcomes.py` |
| Table 5 and Section 4.4, expert check | `80_coder_agreement.py`, `85_validity.py` |
| Table 7, sampling | `10_build_instances.py`, `20_sample_datasets.py` |
| Table 8, intra-annotator agreement | `50_agreement.py --floor` |
| Figures 1 and 2 | `99_figures.py` |

## Names in the paper and in the files

| In the paper | In the files |
|---|---|
| Development set, test set | `d_ref`, `d_test` |
| T1, T1 reworded (control), T2, T3 | runs `r1`, `ctrl`, `r2`, `r3`; guidelines `T1`, `T1plus`, `T2`, `T3` in `specs/` |
| Second run of the same model | `<model>_rep2`, option `--floor` |
| Revision record | `specs/revision_log_T1_T2.yaml`, `specs/revision_log_T2_T3.yaml` |
| Full label | `comp` |
| Layers | `screen`, `olabel`, `op`, `dom`, `pos`, `ext`, `lexsub` |
| Structural domain | `STRUCT` (`SYNT` in T1 and T2) |
| Shared label set | "common space" |
| Diagnosis types priority and over-fine distinction | `Precedence`, `FineGrained` |
| Complex edits | "packaging" |
| Expert check | `outputs/adjudication/`; the 150 edits are "H" |
| Expert 1 (led the design), expert 2 (no part in it) | coder 1, coder 2 (`c2`) |

Table 4 numbers the 17 revisions with a measurable target in the order of
the revision record. Revisions 1 and 2 are RL1-01 and RL1-02. Revisions 3
to 17 are RL2-01 to RL2-17 without RL2-07 and RL2-10. Those two and RL2-18
have no measurable target.

## Contents

| Folder | Contents |
|---|---|
| `specs/` | The guideline of every version, each with its answer-format block (`*_output.md`), and the two revision records |
| `config/` | The five models and their settings, the versions, and the sampling settings |
| `data/` | The source M2 file (MuCGEC development split) and the two samples; see `data/README.md` |
| `scripts/` | The pipeline, numbered in run order |
| `outputs/annotations/` | Raw and normalized labels of every model under every version, including the second runs, with the system prompt and model settings used |
| `outputs/adjudication/` | The expert check: instructions, protocol, both experts' independent sheets, the second expert's sheet after review, the worksheet of the 60 disagreements, and the consensus labels |
| `figures/` | The two figures of the paper |

## Running the models again

`scripts/30_annotate.py` queries the five models. API keys are read from
the environment (see `config/models.yaml`). New labels can differ from the
committed ones, which are the data of the study.

`70_make_h_sheet.py`, `75_make_c2_sheet.py`, and `80_coder_agreement.py
compare --write-worksheet` write blank files over the filled expert files.
Copy the filled files elsewhere first. `reproduce.sh` runs none of them in
that way.

## Copyright and license

Copyright © 2026 The Authors. All rights reserved except as granted below.

- Code in `scripts/` and `config/`, together with `reproduce.sh` and `environment.yml`, is licensed under the [MIT License](LICENSE).
- Original documentation, guidelines, annotations, and other research materials are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
- For these materials, noncommercial use, modification, and redistribution are permitted with attribution. Commercial use, including commercial use of modified or derivative works, is prohibited without prior written permission from the copyright holders.
- Third-party materials, including MuCGEC data, remain subject to their original licenses and terms. Nothing in this repository relicenses those materials.
