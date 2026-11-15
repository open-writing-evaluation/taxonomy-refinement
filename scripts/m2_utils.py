"""Shared utilities: M2 parsing, sentence reconstruction, coverage strata.

The M2 file is jp-errant-zh output (Gu et al., 2025):
  S <space-segmented source tokens>
  A <start> <end>|||<label>|||<correction tokens>|||REQUIRED|||-NONE-|||<annotator_id>
Deletions have an empty correction field. Insertions have start == end.
Labels: R:PINYIN / R:SHAPE / R:MULTI / R:CO / R:WO / R:DE / M:DE / U:DE /
        OP:POS[ POS...][ -> POS[ POS...]] with UD-style POS, PUNCT included.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass

# ---------------------------------------------------------------- trigger sets
# Mutually exclusive trigger sets used by the coverage classifier below.
TRIGGERS = {
    'STR':   {'的', '地', '得'},
    'ASP':   {'了', '着', '过'},
    'MOD':   {'能', '会', '可以', '应该', '必须', '该', '能够', '应当', '敢', '肯'},
    'CONST': {'把', '被', '使'},
    'ADD':   {'都', '也', '凡是'},
    'TEMP':  {'才', '就', '再'},
    'NEG':   {'不', '没'},
    'CONT':  {'却', '反而'},
    'LINK':  {'和', '或者', '还是', '不管', '无论', '不论'},
    'LOC':   {'从', '在', '到'},
    'DEG':   {'比', '真', '一点儿', '一点'},
    'FOC':   {'连'},
    'CLF':   set('个本张条件位只座辆台份斤块支场篇部首双对层间名匹头棵颗杯瓶碗顶幅封架段'),
}


@dataclass
class Edit:
    sent_idx: int
    edit_idx: int          # index within this annotator's edit list for the sentence
    ref_id: int
    start: int             # token offsets in the segmented source
    end: int
    label: str
    correction: str        # space-joined correction tokens ('' = deletion)


@dataclass
class Sentence:
    sent_idx: int
    tokens: list
    edits_by_ref: dict     # ref_id -> [Edit]


def parse_m2(path: str) -> list:
    """Parse an M2 file into a list of Sentence objects."""
    sentences = []
    blocks = io.open(path, encoding='utf8').read().strip().split('\n\n')
    for si, block in enumerate(blocks):
        lines = block.split('\n')
        assert lines[0].startswith('S '), f'bad block {si}'
        tokens = lines[0][2:].split(' ')
        by_ref: dict = {}
        for line in lines[1:]:
            assert line.startswith('A '), f'bad A-line in block {si}: {line!r}'
            parts = line[2:].split('|||')
            if parts[1] in ('noop', 'NA'):
                continue
            start, end = map(int, parts[0].split())
            ref = int(parts[-1])
            e = Edit(sent_idx=si, edit_idx=len(by_ref.get(ref, [])), ref_id=ref,
                     start=start, end=end, label=parts[1],
                     correction=parts[2].strip())
            by_ref.setdefault(ref, []).append(e)
        sentences.append(Sentence(sent_idx=si, tokens=tokens, edits_by_ref=by_ref))
    return sentences


def char_offsets(tokens: list) -> list:
    """Cumulative character start offset of each token in ''.join(tokens)."""
    offs, pos = [], 0
    for t in tokens:
        offs.append(pos)
        pos += len(t)
    offs.append(pos)  # sentinel: offsets[len(tokens)] == total length
    return offs


def apply_edits(tokens: list, edits: list) -> str:
    """Apply one reference's edits to the token list; return corrected text.

    Right-to-left so earlier offsets stay valid. Ties on (start, end) are
    applied in REVERSE listing order (edit_idx descending), so that two
    insertions at the same position end up in their listed order in the
    output -- e.g. MuCGEC s703 lists M:PRON 自己 then M:DE 的 at the same
    index, and the intended text is 自己的, not 的自己.
    """
    toks = list(tokens)
    for e in sorted(edits, key=lambda e: (e.start, e.end, e.edit_idx),
                    reverse=True):
        repl = e.correction.split(' ') if e.correction else []
        toks[e.start:e.end] = repl
    return ''.join(toks)


# ------------------------------------------------------- meta-reference filter
# Some MuCGEC references are annotator meta-comments rather than corrections:
# the "corrected" sentence is literally 没有错误 ('no error') or 无法标注
# ('cannot annotate'). jp-errant-zh aligns these as large spurious edits.
# In the dev file used here all such references carry annotator id 0
# (58 sentences, 126 edits). We exclude the affected sentences entirely.
META_STRINGS = {'没有错误', '无法标注'}
_PUNCT_RE = re.compile(r'[。，、！？；：""''（）\s.!?,;:()「」...-]')


def is_meta_reference(tokens: list, edits: list) -> bool:
    """True if applying this reference's edits yields only a meta-comment."""
    core = _PUNCT_RE.sub('', apply_edits(tokens, edits))
    return core in META_STRINGS


def filter_meta_sentences(sentences: list) -> tuple:
    """Drop sentences in which ANY reference is a meta-comment.

    Returns (kept_sentences, n_excluded).
    """
    kept, excluded = [], 0
    for s in sentences:
        if any(is_meta_reference(s.tokens, ed) for ed in s.edits_by_ref.values()):
            excluded += 1
        else:
            kept.append(s)
    return kept, excluded


def classify(src_tokens, start, end, label, correction) -> str:
    """Mutually exclusive coverage categories (basis for the sampling strata)."""
    if label in ('R:PINYIN', 'R:SHAPE', 'R:MULTI'):
        return 'ORTH-similarity'
    if label == 'R:CO':
        return 'ORTH-order'
    if label == 'R:WO':
        return 'word-order'
    if 'PUNCT' in label:
        return 'ORTH-punctuation'
    src_toks = src_tokens[start:end]
    corr_toks = correction.split(' ') if correction else []
    if len(src_toks) <= 1 and len(corr_toks) <= 1:
        for name, items in TRIGGERS.items():
            if (src_toks and src_toks[0] in items) or (corr_toks and corr_toks[0] in items):
                return 'trigger:' + name
    return 'other'


_OPEN = {'VERB', 'NOUN', 'ADJ', 'PROPN', 'NUM', 'ADV'}
_CLOSED = {'AUX', 'ADP', 'SCONJ', 'CCONJ', 'CONJ', 'DET', 'PART', 'PRON', 'INTJ', 'SYM'}


def _label_pos(label: str) -> set:
    spec = label.split(':', 1)[1] if ':' in label else ''
    return set(t for side in re.split(r'->', spec) for t in side.strip().split() if t)


def stratum(src_tokens, start, end, label, correction) -> str:
    """Sampling strata (coarser than classify; residual split by POS class)."""
    c = classify(src_tokens, start, end, label, correction)
    if c == 'ORTH-similarity':
        return 'orth_sim'
    if c == 'ORTH-punctuation':
        return 'orth_punc'
    if c in ('ORTH-order', 'word-order'):
        return 'wo_co'
    if c == 'trigger:STR':
        return 'trigger_str'
    if c.startswith('trigger:'):
        return 'trigger_other'
    p = _label_pos(label)
    if p and p <= _OPEN:
        return 'residual_open'
    if p and p <= _CLOSED:
        return 'residual_closed'
    return 'residual_mixed'


# ---------------------------------------------- adjudication-sheet utilities
# Full-width -> ASCII normalization for adjudicator-entered cells (gold_* and
# notes only; sentence/edit columns must stay untouched, since full-width
# punctuation is real content there). A Chinese IME naturally produces
# full-width ？ ： ｜ ；, which would otherwise dodge downstream checks.
FW_TRANS = str.maketrans({'？': '?', '：': ':', '｜': '|', '；': ';', '　': ' '})


def parse_alternate(s: str):
    """Normalize one gold_alternates entry to the serialized composite form.

    Accepted spellings (fields |-separated; multiple alternates ;-separated
    at the cell level, split by the caller):
      core:  OP|DOM|POS|EXT        (optional leading CORE|)
      orth:  TRUE|R:ORTH|subtype   (or leading ORTH| instead of TRUE|)
    Also tolerated (colon spelling, as used in the filled coder sheets):
      core:  OP:DOM:POS:EXT        (EXT may itself contain colons,
                                    e.g. R:LEX-FUNC:ADV:TEMP:jiu)
      orth:  TRUE:R:ORTH:subtype   (or leading ORTH: instead of TRUE:)
    Extension items are reduced to their code (DEG:zui -> DEG), matching how
    model answers are serialized. Returns None if unparseable.
    """
    raw = str(s).translate(FW_TRANS).strip()
    parts = [p.strip() for p in raw.split('|') if p.strip()]
    if not parts:
        return None
    if len(parts) == 1 and ':' in raw:
        cp = [p.strip() for p in raw.split(':') if p.strip()]
        if cp and cp[0].upper() in ('ORTH', 'TRUE') and len(cp) >= 3:
            olabel = ':'.join(cp[1:-1]).upper()
            return f'ORTH|{olabel}|{cp[-1].lower()}'
        if len(cp) >= 4 and cp[0].upper() in ('M', 'R', 'U', 'WO', 'CO'):
            op, dom, pos, ext = cp[0], cp[1], cp[2], ':'.join(cp[3:])
            code = ('none' if ext.lower() == 'none'
                    else ext.split(':')[0].upper())
            return f'CORE|{op.upper()}|{dom.upper()}|{pos.upper()}|{code}'
        return None
    head = parts[0].upper()
    if head in ('ORTH', 'TRUE'):
        if len(parts) == 3:
            return f'ORTH|{parts[1].upper()}|{parts[2].lower()}'
        return None
    if head == 'CORE':
        parts = parts[1:]
    if len(parts) == 4:
        op, dom, pos, ext = parts
        code = 'none' if ext.lower() == 'none' else ext.split(':')[0].upper()
        return f'CORE|{op.upper()}|{dom.upper()}|{pos.upper()}|{code}'
    return None


def load_jsonl(path):
    with open(path, encoding='utf8') as f:
        return [json.loads(l) for l in f if l.strip()]


def dump_jsonl(rows, path):
    with open(path, 'w', encoding='utf8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


# Instance-level artifacts of the M2 extraction:
# 1. character-null edits: token re-segmentations with string-identical
#    source and corrected spans (116 edits, all R:MULTI);
# 2. embedded annotator markers: edits inserting a meta-marker such as
#    缺失成分 ('missing component') that the MuCGEC annotator left inside
#    the reference text (3 first-reference edits).
EMBEDDED_MARKERS = ('缺失成分',)


def is_artifact_instance(inst: dict) -> bool:
    if inst['src_span'] == inst['cor_span']:
        return True
    return any(m in inst['cor_span'] or m in inst['src_span']
               for m in EMBEDDED_MARKERS)
