#!/usr/bin/env python3
"""Build the blank blind-adjudication sheet for the fixed subset H.

H = h_n items drawn ONCE from D_test, proportionally over strata with a fixed
seed (selection never depends on agreement status or model output; the set is
frozen before any adjudication). Writes one workbook with a shuffled item
order and NO model labels (blind), plus the frozen id set:

  outputs/adjudication/h_T3_sheet.xlsx   fill using specs/T3_taxonomy.md
  outputs/adjudication/h_ids.json

The released repository ships the FILLED coder-1 sheet at that same path
(and coder 2's copy as h_T3_sheet_c2.xlsx, built by 75_make_c2_sheet.py);
rerunning this script overwrites the sheet with a blank one, so copy the
filled sheets elsewhere first.

Usage:
    python scripts/70_make_h_sheet.py
"""
import argparse
import collections
import json
import os
import random
import sys

import pandas as pd
import yaml
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl, is_artifact_instance
from prompting import mark_span

GOLD_COLS = ['gold_orthographic', 'gold_orth_label', 'gold_orth_subtype',
             'gold_operation', 'gold_domain', 'gold_pos', 'gold_extension']

SPACES = {
    'T3': dict(
        orth_labels='R:ORTH,CO:ORTH,M:ORTH,U:ORTH',
        domains='LEX-CONT,LEX-FUNC,STRUCT',
        extensions=['none', 'STR:de',
                    'ASP:zhe', 'ASP:le', 'ASP:guo', 'ASP:zhe-le', 'ASP:zhe-guo', 'ASP:le-guo',
                    'TEMP:cai', 'TEMP:jiu', 'TEMP:zai', 'TEMP:cai-jiu', 'TEMP:cai-zai', 'TEMP:jiu-zai',
                    'ADD:ye', 'ADD:dou', 'ADD:fanshi', 'ADD:ye-dou',
                    'CONT:que', 'CONT:faner', 'CONT:que-faner',
                    'LINK:he', 'LINK:huozhe', 'LINK:haishi', 'LINK:huozhe-haishi', 'LINK:buguan', 'LINK:wulun',
                    'DEG:zhen', 'DEG:yidianr', 'DEG:bi',
                    'LOC:cong', 'LOC:zai', 'LOC:dao', 'LOC:cong-zai', 'LOC:cong-dao', 'LOC:zai-dao',
                    'LOC:shang', 'LOC:zhong',
                    'MOD:neng', 'MOD:hui', 'MOD:keyi', 'MOD:yinggai', 'MOD:bixu', 'MOD:yao', 'MOD:xiang',
                    'MOD:neng-hui', 'MOD:neng-keyi', 'MOD:hui-keyi',
                    'FOC:lian-dou', 'FOC:lian-ye',
                    'CONST:ba', 'CONST:bei', 'CONST:shi',
                    'ARG:object', 'ARG:subject',
                    'COMP:result', 'COMP:duration', 'COMP:directional', 'COMP:potential', 'COMP:degree',
                    'NEG:bu', 'NEG:mei', 'NEG:bu-mei',
                    'CLF:ge', 'CLF:ben', 'CLF:zhang', 'CLF:tiao', 'CLF:ge-ben',
                    'MIX:ba-bei', 'MIX:bei-shou'],
        guide_rule=('T3 rules: judge with specs/T3_taxonomy.md open. '
                    'Deterministic domain rule (M/U/WO -> STRUCT; R never '
                    'STRUCT); packaging order: WO test, containment, '
                    'entangled movement, cascade locality, rewording rule; '
                    'head rule + pro-form/localizer/NUM-CLF POS conventions; '
                    'ARG only for arguments of a stable predicate; prefer '
                    'none for unlisted phenomena.')),
}


def style(xlsx_path, n_rows, space, models_note):
    cfg = SPACES[space]
    wb = load_workbook(xlsx_path)
    ws = wb['adjudication']
    header = {c.value: c.column for c in ws[1]}
    for cell in ws[1]:
        cell.font = Font(name='Arial', bold=True, size=10)
    ws.freeze_panes = 'A2'
    widths = {'id': 15, 'source_marked': 55, 'corrected': 55, 'edit': 26,
              'gold_orthographic': 16, 'gold_orth_label': 14,
              'gold_orth_subtype': 15, 'gold_operation': 13,
              'gold_domain': 13, 'gold_pos': 10, 'gold_extension': 16,
              'gold_alternates': 22, 'uncertain': 11, 'notes': 28}
    for name, col in header.items():
        ws.column_dimensions[get_column_letter(col)].width = widths.get(name, 14)
    wrap = Alignment(wrap_text=True, vertical='top')
    yellow = PatternFill('solid', fgColor='FFFF00')
    for row in ws.iter_rows(min_row=2, max_row=n_rows + 1):
        for cell in row:
            cell.font = Font(name='Arial', size=10)
            cell.alignment = wrap
    for name in GOLD_COLS + ['uncertain']:
        col = get_column_letter(header[name])
        for r in range(2, n_rows + 2):
            ws[f'{col}{r}'].fill = yellow

    lists = wb.create_sheet('lists')
    for i, v in enumerate(cfg['extensions'], start=1):
        lists.cell(row=i, column=1, value=v)
    lists.sheet_state = 'hidden'
    inline = {
        'gold_orthographic': 'TRUE,FALSE',
        'gold_orth_label': cfg['orth_labels'],
        'gold_orth_subtype': 'phon,shape,complex,order,punc',
        'gold_operation': 'M,R,U,WO',
        'gold_domain': cfg['domains'],
        'gold_pos': 'VERB,NOUN,ADJ,ADV,PART,AUX,PREP,CLF,CONJ,X',
        'uncertain': 'yes',
    }
    for name, values in inline.items():
        dv = DataValidation(type='list', formula1=f'"{values}"',
                            allow_blank=True, showErrorMessage=True,
                            error='Pick a value from the list.',
                            errorTitle='Invalid value')
        ws.add_data_validation(dv)
        col = get_column_letter(header[name])
        dv.add(f'{col}2:{col}{n_rows + 1}')
    dv_ext = DataValidation(
        type='list', formula1=f"=lists!$A$1:$A${len(cfg['extensions'])}",
        allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv_ext)
    col = get_column_letter(header['gold_extension'])
    dv_ext.add(f'{col}2:{col}{n_rows + 1}')

    g = wb.create_sheet('guide')
    g.column_dimensions['A'].width = 24
    g.column_dimensions['B'].width = 115
    guide = [
        (f'Blind adjudication under {space}', ''),
        ('1.', 'Judge the marked edit only, relative to the given corrected sentence, using ONLY the written guideline for this version.'),
        ('2.', cfg['guide_rule']),
        ('3.', 'Orthographic rows: fill gold_orth_label + subtype only. Core rows: operation/domain/pos/extension.'),
        ('4.', 'gold_alternates: other labels you would also accept (| separated: CORE|OP|DOM|POS|EXTCODE or ORTH|LABEL|subtype; multiple alternates ; separated).'),
        ('5.', 'uncertain = yes marks items to resolve against the guideline on a second pass BEFORE any model output is unsealed.'),
        ('6.', models_note),
    ]
    for i, (a, b) in enumerate(guide, start=1):
        ca, cb = g.cell(row=i, column=1, value=a), g.cell(row=i, column=2, value=b)
        ca.font = Font(name='Arial', size=10, bold=(b == '' and a != ''))
        cb.font = Font(name='Arial', size=10)
        cb.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(xlsx_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config/rounds.yaml')
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))['adjudication']
    rows_all = [r for r in load_jsonl(cfg['source'])
                if not is_artifact_instance(r)]
    rng = random.Random(cfg['seed'])

    # proportional allocation over strata (largest-remainder)
    by_st = collections.defaultdict(list)
    for r in rows_all:
        by_st[r['stratum']].append(r)
    n_total = len(rows_all)
    h_n = cfg['h_n']
    quotas, remainders = {}, []
    used = 0
    for st, pool in sorted(by_st.items()):
        exact = h_n * len(pool) / n_total
        quotas[st] = int(exact)
        used += int(exact)
        remainders.append((exact - int(exact), st))
    for _, st in sorted(remainders, reverse=True)[:h_n - used]:
        quotas[st] += 1
    chosen = []
    for st, pool in sorted(by_st.items()):
        pool = sorted(pool, key=lambda r: r['id'])
        rng.shuffle(pool)
        chosen += pool[:quotas[st]]

    outdir = os.path.join('outputs', 'adjudication')
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'h_ids.json'), 'w') as f:
        json.dump({'seed': cfg['seed'], 'n': len(chosen),
                   'ids': sorted(r['id'] for r in chosen),
                   'strata': dict(collections.Counter(
                       r['stratum'] for r in chosen))}, f, indent=2)

    for space in ('T3',):
        order = list(chosen)
        random.Random(f"{cfg['seed']}_{space}").shuffle(order)  # independent orders
        rows = []
        for inst in order:
            s, e = inst['char_start'], inst['char_end']
            if s == e:
                edit = f'INSERT 「{inst["cor_span"]}」'
            elif not inst['cor_span']:
                edit = f'DELETE 「{inst["src_span"]}」'
            else:
                edit = f'「{inst["src_span"]}」 -> 「{inst["cor_span"]}」'
            rows.append({'id': inst['id'],
                         'source_marked': mark_span(inst['src_text'], s, e),
                         'corrected': inst['cor_text'], 'edit': edit,
                         **{c: '' for c in GOLD_COLS},
                         'gold_alternates': '', 'uncertain': '', 'notes': ''})
        df = pd.DataFrame(rows)
        csv_path = os.path.join(outdir, f'h_{space}_sheet.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        xlsx_path = os.path.join(outdir, f'h_{space}_sheet.xlsx')
        df.to_excel(xlsx_path, index=False, sheet_name='adjudication',
                    engine='openpyxl')
        style(xlsx_path, len(rows), space,
              'Model outputs are never shown in this sheet; adjudicate from the guideline alone.')
        print(f'{len(rows)} items -> {xlsx_path}')
    print('strata:', dict(collections.Counter(r['stratum'] for r in chosen)))


if __name__ == '__main__':
    main()
