# Annotation task: blind adjudication of 150 Chinese learner-error edits

You will label 150 pre-extracted edits from Chinese learner sentences under
a written annotation guideline. Total time is about 3–4 hours, in this
order:

1. **Read the guideline** (`T3_taxonomy.md`): ~40–50 minutes. It defines
   every label and decision rule you need, with worked examples. Your
   labels must come from this document alone.
2. **Warm up** on `h_T3_calibration_10.xlsx` (10 practice items): ~15
   minutes. These are for learning the sheet format and the rules; they
   are not scored.
3. **Fill your copy of the sheet** (150 items): ~2–3 hours. Coder 1 fills
   `h_T3_sheet.xlsx`; coder 2 fills `h_T3_sheet_c2.xlsx`. This is the file
   you return.

## How to fill the sheet

Each row shows a learner sentence with one edit marked (【】 around replaced
or deleted text, ▲ at an insertion point), the corrected sentence, and the
edit itself. Judge **only the marked edit**, relative to the given corrected
sentence.

- First decide `gold_orthographic` (TRUE/FALSE): is this purely an
  orthographic (writing-form) error, per the guideline's screening rule?
  - If **TRUE**: fill `gold_orth_label` and `gold_orth_subtype` only.
  - If **FALSE**: fill `gold_operation`, `gold_domain`, `gold_pos`, and
    `gold_extension` (choose `none` when no extension code applies).
- Yellow cells are the ones to fill; most have dropdown lists. The `guide`
  tab inside the workbook repeats the key rules.
- `gold_alternates`: if a second reading is genuinely defensible under the
  guideline, record it there (format is in the guide tab); leave empty
  otherwise.
- `uncertain`: mark `yes` on a first pass if unsure, then return to those
  rows and settle them yourself against the guideline text before sending
  the file back. It is fine for some `uncertain=yes` marks to remain in the
  returned file as a record; just make sure every row has your final label.
- `notes`: optional, anything you want to flag.

## Ground rules (please read carefully)

- Work **alone and only from the written guideline**. Please do not use any
  AI assistant, machine translation, search engine, or another person for
  any item, and do not discuss any item with anyone (including the other
  coder) until you have returned the completed sheet. This independence is
  the point of the exercise.
- If a guideline passage itself is unclear, you may ask which section
  applies; the answer will only point to guideline text, and the question
  will be logged. Do not describe specific items when asking.
- Work in the given row order; do not sort, delete, or add rows.
- Save the file as .xlsx under the same name and return it when every row
  is complete.

There are no "gotcha" items and no expected answers to guess; label exactly
what the guideline tells you. If two answers seem defensible, pick the one
the guideline supports best and put the other in `gold_alternates`.
