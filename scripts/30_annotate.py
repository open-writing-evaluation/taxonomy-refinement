#!/usr/bin/env python3
"""Run the LLM annotator panel over an instance file.

Each (model, run_tag) writes outputs/annotations/<run_id>/<model_id><tag>.jsonl
with one row per instance: raw response, parsed JSON (or null), status.
Already-annotated instance ids are skipped, so the script is resumable.

Provider notes:
* anthropic / claude-sonnet-5: sampling parameters (temperature, top_p, top_k)
  are rejected with a 400 and are never sent; adaptive thinking is on by
  default (set `thinking: "disabled"` in config to turn it off).
* openai / gpt-5.6-terra: no temperature; `reasoning_effort` is pinned via
  config; uses max_completion_tokens (reasoning tokens count against it).
* together (Qwen/DeepSeek/Kimi): standard sampling, temperature 0.

Usage:
    export ANTHROPIC_API_KEY=... OPENAI_API_KEY=... TOGETHER_API_KEY=...
    python scripts/30_annotate.py --instances data/samples/d_ref.jsonl \
        --spec specs/T1_taxonomy.md --run-id r1
    # repeat runs for the within-model reliability floor:
    python scripts/30_annotate.py --instances data/samples/d_ref.jsonl \
        --spec specs/T1_taxonomy.md --run-id r1 --tag _rep2
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import threading

import yaml
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(__file__))
from m2_utils import load_jsonl
from prompting import build_system_prompt, render_instance

_write_lock = threading.Lock()


def make_client(provider):
    if provider == 'anthropic':
        import anthropic
        return anthropic.Anthropic()
    from openai import OpenAI
    if provider == 'openai':
        return OpenAI()
    if provider == 'together':
        return OpenAI(base_url='https://api.together.xyz/v1',
                      api_key=os.environ['TOGETHER_API_KEY'])
    raise ValueError(provider)


def call_model(client, mcfg, system, user, timeout, history=None):
    provider = mcfg['provider']
    params = dict(mcfg.get('params', {}))
    msgs = list(history or []) + [{'role': 'user', 'content': user}]
    if provider == 'anthropic':
        kwargs = {}
        if mcfg.get('thinking') == 'disabled':
            kwargs['thinking'] = {'type': 'disabled'}
        resp = client.messages.create(
            model=mcfg['model'],
            system=[{'type': 'text', 'text': system,
                     'cache_control': {'type': 'ephemeral'}}],
            messages=msgs,
            max_tokens=params.get('max_tokens', 4000),
            timeout=timeout, **kwargs)
        texts = [b.text for b in resp.content if getattr(b, 'type', '') == 'text']
        return '\n'.join(texts), getattr(resp, 'stop_reason', None)
    # OpenAI-compatible chat completions (openai + together)
    if mcfg.get('stream'):
        # some Together models (e.g. Qwen3.7-Max) are streaming-only
        chunks = client.chat.completions.create(
            model=mcfg['model'],
            messages=[{'role': 'system', 'content': system}] + msgs,
            timeout=timeout, stream=True, **params)
        parts, finish = [], None
        for ch in chunks:
            if not getattr(ch, 'choices', None):
                continue
            c = ch.choices[0]
            delta = getattr(c, 'delta', None)
            if delta is not None and getattr(delta, 'content', None):
                parts.append(delta.content)
            if getattr(c, 'finish_reason', None):
                finish = c.finish_reason
        return ''.join(parts), finish
    resp = client.chat.completions.create(
        model=mcfg['model'],
        messages=[{'role': 'system', 'content': system}] + msgs,
        timeout=timeout, **params)
    choice = resp.choices[0]
    return choice.message.content, getattr(choice, 'finish_reason', None)


def extract_json(text):
    """Return the last parseable flat JSON object in the text.

    Robust to reasoning traces or commentary around the answer; the output
    schema is flat, so nested-brace objects inside thinking text are skipped
    unless they parse as a dict.
    """
    if text is None:
        return None
    try:
        obj = json.loads(text.strip())
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    last = None
    for m in re.finditer(r'\{[^{}]*\}', text, re.DOTALL):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                last = obj
        except json.JSONDecodeError:
            continue
    return last


REPAIR_MSG = ('Your previous reply was not a single valid JSON object matching '
              'the required schema. Reply again with ONLY the corrected JSON object.')


def annotate_one(client, mcfg, system, inst, timeout, retries):
    @retry(stop=stop_after_attempt(retries),
           wait=wait_exponential(multiplier=2, min=2, max=60), reraise=True)
    def _call(user, history=None):
        return call_model(client, mcfg, system, user, timeout, history)

    user = render_instance(inst)
    raw, finish = _call(user)
    parsed = extract_json(raw)
    status = 'ok'
    if parsed is None:
        raw2, finish = _call(REPAIR_MSG, history=[
            {'role': 'user', 'content': user},
            {'role': 'assistant', 'content': raw or ''}])
        parsed = extract_json(raw2)
        status = 'repaired' if parsed is not None else 'protocol_error'
        raw = raw2 if parsed is not None else raw
    return {'id': inst['id'], 'raw': raw, 'annotation': parsed, 'status': status,
            'finish': finish}


def run_model(mcfg, instances, system, req, outdir, tag, retry_failed=False):
    out_path = os.path.join(outdir, f"{mcfg['id']}{tag}.jsonl")
    done = set()
    if os.path.exists(out_path):
        rows = {r['id']: r for r in load_jsonl(out_path)}  # last row per id wins
        if retry_failed:
            done = {i for i, r in rows.items()
                    if r['status'] in ('ok', 'repaired')}
        else:
            done = set(rows)
    todo = [i for i in instances if i['id'] not in done]
    if not todo:
        print(f"{mcfg['id']}{tag}: all {len(instances)} done.")
        return
    client = make_client(mcfg['provider'])

    def work(inst):
        try:
            row = annotate_one(client, mcfg, system, inst,
                               req['timeout_s'], req['max_retries'])
        except Exception as ex:  # terminal API failure after retries
            row = {'id': inst['id'], 'raw': f'ERROR: {ex}', 'annotation': None,
                   'status': 'api_error'}
        with _write_lock:
            with open(out_path, 'a', encoding='utf8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        return row['status']

    with cf.ThreadPoolExecutor(max_workers=req['max_workers']) as ex:
        statuses = list(tqdm(ex.map(work, todo), total=len(todo),
                             desc=f"{mcfg['id']}{tag}"))
    print(f"{mcfg['id']}{tag}: " + ', '.join(
        f'{s}={statuses.count(s)}' for s in sorted(set(statuses))))
    # post-run diagnostics: surface the first API error and truncation hints
    rows = {r['id']: r for r in load_jsonl(out_path)}
    errs = [r for r in rows.values() if r['status'] == 'api_error']
    if errs:
        print(f"  first api_error: {errs[0]['raw'][:300]}")
    trunc = sum(1 for r in rows.values()
                if r['status'] == 'protocol_error'
                and r.get('finish') in ('length', 'max_tokens'))
    if trunc:
        print(f"  NOTE: {trunc} protocol errors hit the token limit "
              f"(finish=length) - raise max_tokens for this model.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instances', required=True)
    ap.add_argument('--spec', required=True,
                    help='taxonomy guideline, e.g. specs/T1_taxonomy.md')
    ap.add_argument('--run-id', required=True,
                    help='e.g. r1; output dir outputs/annotations/<run-id>')
    ap.add_argument('--models-config', default='config/models.yaml')
    ap.add_argument('--only', default=None, help='comma list of model ids')
    ap.add_argument('--tag', default='', help='suffix for repeat runs, e.g. _rep2')
    ap.add_argument('--limit', type=int, default=None,
                    help='annotate only the first N instances (pilot runs)')
    ap.add_argument('--retry-failed', action='store_true',
                    help='re-run instances whose last stored status is '
                         'api_error or protocol_error (appended rows '
                         'supersede old ones downstream)')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.models_config))
    models = cfg['models']
    if args.only:
        keep = set(args.only.split(','))
        models = [m for m in models if m['id'] in keep]
    for m in models:
        if 'PIN_ME' in m['model']:
            sys.exit(f"Model '{m['id']}' is not pinned yet - edit config/models.yaml.")

    instances = load_jsonl(args.instances)
    if args.limit:
        instances = instances[:args.limit]
    system = build_system_prompt(args.spec)
    outdir = os.path.join('outputs', 'annotations', args.run_id)
    os.makedirs(outdir, exist_ok=True)
    # persist the exact prompt and panel config used for this run
    with open(os.path.join(outdir, 'system_prompt.txt'), 'w', encoding='utf8') as f:
        f.write(system)
    with open(os.path.join(outdir, 'panel_config.json'), 'w') as f:
        json.dump(cfg, f, indent=2)
    for m in models:
        run_model(m, instances, system, cfg['request'], outdir, args.tag,
                  retry_failed=args.retry_failed)


if __name__ == '__main__':
    main()
