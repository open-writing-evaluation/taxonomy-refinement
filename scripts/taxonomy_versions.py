"""Taxonomy version registry: inventories, validation, serialization, crosswalk.

Versions:
  T1   initial version: SYNT; judgment-based domain assignment for R AND
       M/U ("affecting structure"); WO dual-use; LEX:syn/colloc/coinage
       refinements; 15 ext codes; no MOD/CLF
  T1P  instruction-only control: identical label space to T1
  T2   second version: SYNT; M/U/WO=>SYNT convention (R still
       judgment-based); WO dual-use; LEX:* removed; 14 ext codes
  T3   endpoint (STRUCT; CO; deterministic R-never-STRUCT; +MOD +CLF;
       ARG/CONST split) + packaging guidelines.

The crosswalk maps earlier spaces into the final space so confusion
structures are comparable across rounds, following the logged renames:
SYNT->STRUCT, WO:ORTH->CO:ORTH, and LEX:* -> none (refinement removed).
Extension analysis is otherwise code-level.
"""
from __future__ import annotations

import os
import yaml

POS = {'VERB', 'NOUN', 'ADJ', 'ADV', 'PART', 'AUX', 'PREP', 'CLF', 'CONJ', 'X'}
OPS = {'M', 'R', 'U', 'WO'}
ORTH_SUBS = {'phon', 'shape', 'complex', 'order', 'punc'}
# any OP:ORTH string is *parseable* in every version; validity marks whether
# the label form is licensed by the version's schema (out-of-schema forms are
# kept as ordinary label values with a note - they are annotation behavior,
# not protocol failure).
ORTH_OPS_PARSEABLE = {'M', 'R', 'U', 'WO', 'CO'}

VERSIONS = {
    'T1': dict(
        doms={'LEX-CONT', 'LEX-FUNC', 'SYNT'},
        orth_labels={'R:ORTH', 'WO:ORTH'},
        ext_codes={'TEMP', 'ADD', 'CONT', 'LINK', 'DEG', 'LOC', 'ASP', 'FOC',
                   'CONST', 'ARG', 'COMP', 'STR', 'NEG', 'MIX', 'LEX'},
        dom_synonyms={'STRUCT': 'SYNT', 'STRUCTURAL': 'SYNT',
                      'SYNTACTIC': 'SYNT', 'SYNTAX': 'SYNT'},
        # deterministic components of the domain rule stated by this version:
        rule={'muwo_dom': None, 'r_never': None},   # fully judgment-based
    ),
    'T2': dict(
        doms={'LEX-CONT', 'LEX-FUNC', 'SYNT'},
        orth_labels={'R:ORTH', 'WO:ORTH'},
        ext_codes={'TEMP', 'ADD', 'CONT', 'LINK', 'DEG', 'LOC', 'ASP', 'FOC',
                   'CONST', 'ARG', 'COMP', 'STR', 'NEG', 'MIX'},
        dom_synonyms={'STRUCT': 'SYNT', 'STRUCTURAL': 'SYNT',
                      'SYNTACTIC': 'SYNT', 'SYNTAX': 'SYNT'},
        rule={'muwo_dom': 'SYNT', 'r_never': None},  # convention for M/U/WO only
    ),
    'T3': dict(   # endpoint label space
        doms={'LEX-CONT', 'LEX-FUNC', 'STRUCT'},
        orth_labels={'R:ORTH', 'CO:ORTH', 'M:ORTH', 'U:ORTH'},
        ext_codes={'TEMP', 'ADD', 'CONT', 'LINK', 'DEG', 'LOC', 'ASP', 'MOD',
                   'FOC', 'CONST', 'ARG', 'COMP', 'STR', 'NEG', 'CLF', 'MIX'},
        dom_synonyms={'SYNT': 'STRUCT', 'SYNTACTIC': 'STRUCT',
                      'STRUCTURAL': 'STRUCT', 'SYNTAX': 'STRUCT'},
        rule={'muwo_dom': 'STRUCT', 'r_never': 'STRUCT'},
    ),
}
VERSIONS['T1P'] = VERSIONS['T1']

DOM_SEP_SYNONYMS = {'LEX_CONT': 'LEX-CONT', 'LEXCONT': 'LEX-CONT',
                    'LEX_FUNC': 'LEX-FUNC', 'LEXFUNC': 'LEX-FUNC'}
POS_SYNONYMS = {'ADP': 'PREP', 'CCONJ': 'CONJ', 'SCONJ': 'CONJ',
                'PARTICLE': 'PART', 'CLASSIFIER': 'CLF', 'AUXILIARY': 'AUX',
                'PRON': 'NOUN', 'PROPN': 'NOUN', 'NUM': 'X'}
SUB_SYNONYMS = {'phonological': 'phon', 'phonetic': 'phon', 'visual': 'shape',
                'punctuation': 'punc', 'character-order': 'order'}


def load_rounds(path='config/rounds.yaml'):
    return yaml.safe_load(open(path))


def version_of_run(run_id, rounds_cfg=None, path='config/rounds.yaml'):
    cfg = rounds_cfg or load_rounds(path)
    base = run_id
    if base not in cfg['rounds']:
        raise SystemExit(f'unknown run id {run_id!r}; add it to config/rounds.yaml')
    return cfg['rounds'][base]['taxonomy']


def norm_one(row, version):
    """Normalize one raw annotation row into the flat analysis record.

    Conservative, fully-logged normalization. valid=False rows are
    protocol errors. Out-of-schema but well-formed label
    values (e.g. M:ORTH under T1, an extension code outside the version's
    inventory) are kept as label values with valid=True and a `nonschema` note,
    so that the disagreement they create is analyzed as annotation behavior
    and tabulated separately by the diagnosis tooling.
    """
    v = VERSIONS[version]
    a = row.get('annotation')
    out = {'id': row['id'], 'valid': False, 'screen': None, 'olabel': None,
           'osub': None, 'op': None, 'dom': None, 'pos': None, 'ext': None,
           'ext_code': None, 'note': ''}
    notes = []
    if not isinstance(a, dict):
        out['note'] = row.get('status', 'protocol_error')
        return out
    screen = a.get('orthographic')
    if isinstance(screen, str):
        screen = screen.strip().lower() in ('true', 'yes', '1')
        notes.append('screen-coerced')
    if screen is True:
        lab = str(a.get('label', '')).upper().replace(' ', '')
        sub = str(a.get('subtype', '')).strip().lower()
        sub = SUB_SYNONYMS.get(sub, sub)
        if sub.startswith('orth:'):
            sub = sub[5:]
            notes.append('subtype-prefix-stripped')
        parts = lab.split(':')
        wellformed = (len(parts) == 2 and parts[0] in ORTH_OPS_PARSEABLE
                      and parts[1] == 'ORTH' and sub in ORTH_SUBS)
        if wellformed:
            if lab not in v['orth_labels']:
                notes.append(f'nonschema-orth:{lab}')
            out.update(valid=True, screen=True, olabel=lab, osub=sub,
                       note=';'.join(notes))
        else:
            out['note'] = f'bad-orth:{lab}/{sub}'
        return out
    if screen is False:
        op = str(a.get('operation', '')).upper().strip()
        dom = str(a.get('domain', '')).upper().strip()
        dom = DOM_SEP_SYNONYMS.get(dom.replace('-', '_'), dom.replace('_', '-'))
        dom = v['dom_synonyms'].get(dom, dom)
        if dom in v['dom_synonyms'].values() and dom != str(a.get('domain', '')).upper().strip().replace('_', '-'):
            notes.append('dom-mapped')
        pos = str(a.get('pos', '')).upper().strip()
        if pos in POS_SYNONYMS:
            notes.append(f'pos-mapped:{pos}')
            pos = POS_SYNONYMS[pos]
        ext = a.get('extension', 'none')
        ext = 'none' if ext in (None, '', 'None', 'NONE', 'null', '---', 'none') else str(ext).strip()
        code = None
        if ext != 'none':
            code = ext.split(':')[0].upper()
            item = ext.split(':', 1)[1].strip().lower() if ':' in ext else ''
            ext = f'{code}:{item}' if item else code
        ALL_CODES = (VERSIONS['T3']['ext_codes'] | {'LEX'})  # superset
        if op in OPS and dom in v['doms'] and pos in POS and \
                (ext == 'none' or code in ALL_CODES):
            if ext != 'none' and code not in v['ext_codes']:
                notes.append(f'nonschema-ext:{code}')
            out.update(valid=True, screen=False, op=op, dom=dom, pos=pos,
                       ext=ext, ext_code=(code if ext != 'none' else 'none'),
                       note=';'.join(notes))
        else:
            out['note'] = f'bad-core:{op}/{dom}/{pos}/{ext}'
        return out
    out['note'] = 'missing-screen-decision'
    return out


# ---------------------------------------------------------------- crosswalk
def crosswalk_record(r, version):
    """Map a normalized record from `version` space into the final (T3)
    space, following the logged renames/removals. Identity for T3."""
    if version == 'T3' or not r.get('valid'):
        return r
    c = dict(r)
    if c['screen'] is True and c['olabel'] == 'WO:ORTH':
        c['olabel'] = 'CO:ORTH'                       # Split/Rename (CO)
    if c['screen'] is False and c['dom'] == 'SYNT':
        c['dom'] = 'STRUCT'                           # Rename SYNT->STRUCT
    if c['screen'] is False and c.get('ext_code') == 'LEX':
        c['ext_code'], c['ext'] = 'none', 'none'      # RemoveLabel LEX:*
    return c


def serialize(r):
    if r['screen'] is True:
        return f"ORTH|{r['olabel']}|{r['osub']}"
    return f"CORE|{r['op']}|{r['dom']}|{r['pos']}|{r['ext_code']}"


def layer_value(r, layer):
    if layer == 'screen':
        return 'ORTH' if r['screen'] else 'CORE'
    if layer == 'olabel':
        return f"{r['olabel']}|{r['osub']}" if r['screen'] else None
    if layer == 'comp':
        return serialize(r)
    if layer == 'lexsub':
        # sub-label within the LEX refinement (T1 space); defined only when
        # this annotator used a LEX:* code
        if r['screen'] is False and r.get('ext_code') == 'LEX':
            ext = r.get('ext') or ''
            return ext.split(':', 1)[1] if ':' in ext else 'unspecified'
        return None
    key = 'ext_code' if layer == 'ext' else layer
    return (None if r['screen'] else r[key])
