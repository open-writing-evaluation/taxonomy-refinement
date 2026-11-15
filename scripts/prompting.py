"""Prompt construction: the taxonomy specification IS the guideline/prompt.

Each taxonomy version's system prompt is composed as
    PREAMBLE + <spec file> + "\n\n" + <sibling *_output.md block>
The exact prompt used for each round is archived at
outputs/annotations/<run>/system_prompt.txt. The instance rendering is
identical across all rounds; only the taxonomy text changes (protocol
constancy across rounds).
"""
from __future__ import annotations

import os

PREAMBLE = (
    'You are an expert annotator of grammatical errors in Chinese learner '
    'writing. Apply the annotation scheme below to the single edit presented '
    'by the user. Follow the decision procedure exactly; when the guideline '
    'gives a deterministic rule, the rule takes precedence over intuition.\n\n'
)


def output_block_path(spec_path: str) -> str:
    stem = os.path.basename(spec_path)
    stem = stem.replace('_taxonomy.md', '')
    return os.path.join(os.path.dirname(spec_path), f'{stem}_output.md')


def build_system_prompt(spec_path: str) -> str:
    spec = open(spec_path, encoding='utf8').read()
    block = open(output_block_path(spec_path), encoding='utf8').read().strip()
    return PREAMBLE + spec + '\n\n' + block


def mark_span(text: str, start: int, end: int) -> str:
    """Mark the edit span in the source sentence; ▲ marks an insertion point."""
    if start == end:
        return text[:start] + '▲' + text[start:]
    return text[:start] + '【' + text[start:end] + '】' + text[end:]


def render_instance(inst: dict) -> str:
    src, cor = inst['src_text'], inst['cor_text']
    s, e = inst['char_start'], inst['char_end']
    marked = mark_span(src, s, e)
    if s == e:  # insertion
        edit_desc = f'在 ▲ 处插入「{inst["cor_span"]}」'
    elif not inst['cor_span']:  # deletion
        edit_desc = f'删除「{inst["src_span"]}」'
    else:
        edit_desc = f'将「{inst["src_span"]}」改为「{inst["cor_span"]}」'
    return (
        f'学习者原句：{src}\n'
        f'修改后句子（本次参考答案）：{cor}\n'
        f'待标注编辑（在原句中以【】或▲标出）：{marked}\n'
        f'编辑内容：{edit_desc}\n\n'
        'Annotate THIS edit only, relative to THIS corrected sentence. '
        'Reply with the JSON object only.'
    )
