#!/usr/bin/env python3
"""The paper's two figures, in grayscale.

  fig_agreement.pdf  Agreement on the full label (Fleiss' kappa with its 95%
                     bootstrap interval) under T1, T2, T3, and the reworded
                     T1 used as the wording-only control.
  fig_outcomes.pdf   Four panels on revision outcomes: one confusion that
                     falls (resolve), a pair of confusions where one falls
                     and its neighbor rises (relocate), and the share of
                     annotations on modal edits that use the modality
                     label, which exists only from T3 (reveal).

One encoding throughout: development set = black, solid line, filled
circles; test set = gray, dashed line, open squares.

Reads the outputs of 50_agreement.py, 55_confusion.py, and
97_revision_outcomes.py. Writes vector PDF files.

Usage:
    python scripts/99_figures.py --out figures
"""
import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

MODELS = ['claude', 'gpt', 'qwen', 'deepseek', 'kimi']
PANEL = '+'.join(MODELS)
RES = os.path.join('outputs', 'results')
SAMPLES = {'dev': 'd_ref', 'test': 'd_test'}
STYLE = {'dev': dict(color='black', linestyle='-', marker='o', markerfacecolor='black',
                     label='Development set'),
         'test': dict(color='#666666', linestyle='--', marker='s', markerfacecolor='white',
                      label='Test set')}
VERSIONS = [('r1', 'T1'), ('r2', 'T2'), ('r3', 'T3')]
INK, MUTED, GRID = '#222222', '#555555', '#dddddd'
NO_DATE = {'CreationDate': None}     # so that a new run rewrites identical files


def use_times():
    """Use a Times-like face when one is installed, to match the paper."""
    for path in font_manager.findSystemFonts():
        if 'texgyretermes' in os.path.basename(path).lower():
            font_manager.fontManager.addfont(path)
    names = {f.name for f in font_manager.fontManager.ttflist}
    family = next((n for n in ('TeX Gyre Termes', 'Times New Roman', 'Nimbus Roman', 'Liberation Serif')
                   if n in names), 'serif')
    plt.rcParams.update({'font.family': family, 'font.size': 8, 'axes.linewidth': 0.6,
                         'axes.edgecolor': MUTED, 'xtick.color': INK, 'ytick.color': INK,
                         'axes.labelcolor': INK, 'text.color': INK, 'pdf.fonttype': 42,
                         'mathtext.fontset': 'stix'})


def tidy(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=2.5, width=0.6)


def kappa(run, sample):
    cell = json.load(open(os.path.join(RES, f'{run}_agreement.{SAMPLES[sample]}.{PANEL}.json')))['table']['comp']
    return cell['fleiss'], cell['fleiss_ci']


def confusion_pct(run, sample, layer, pair):
    pj = json.load(open(os.path.join(RES, f'{run}_confusion.{SAMPLES[sample]}.final', 'pairs.json')))
    comparisons = pj['n_items'] * len(MODELS) * (len(MODELS) - 1) // 2
    return 100 * pj['pairs'][layer].get(pair, 0) / comparisons


def modality_label_use(sample):
    """% of the annotations of modal edits that use the modality label, under T1, T2, T3."""
    summary = json.load(open(os.path.join(RES, 'revision_outcomes.json')))['summary']
    return summary['modality_label_use_pct'][sample]


def fig_agreement(out):
    fig, ax = plt.subplots(figsize=(3.03, 1.95))
    xs = [1, 2, 3]
    control_x, shift = 4.15, {'dev': -0.05, 'test': 0.05}
    for sample in ('dev', 'test'):
        st = STYLE[sample]
        ks, lo, hi = [], [], []
        for run, _ in VERSIONS:
            k, ci = kappa(run, sample)
            ks.append(k); lo.append(k - ci[0]); hi.append(ci[1] - k)
        x = [v + shift[sample] for v in xs]
        ax.errorbar(x, ks, yerr=[lo, hi], color=st['color'], linestyle=st['linestyle'],
                    marker=st['marker'], markerfacecolor=st['markerfacecolor'],
                    markersize=4.5, linewidth=1.3, capsize=2, elinewidth=0.8,
                    markeredgewidth=0.9, label=st['label'])
        k, ci = kappa('ctrl', sample)
        ax.errorbar([control_x + shift[sample]], [k], yerr=[[k - ci[0]], [ci[1] - k]],
                    color=st['color'], linestyle='none', marker=st['marker'],
                    markerfacecolor=st['markerfacecolor'], markersize=4.5, capsize=2,
                    elinewidth=0.8, markeredgewidth=0.9)
    ax.axvline(3.58, color=MUTED, linewidth=0.6, linestyle=':')
    ax.set_xticks(xs + [control_x])
    ax.set_xticklabels(['T1', 'T2', 'T3', 'T1 reworded\n(control)'])
    ax.set_xlim(0.6, 4.75)
    ax.set_ylim(0.45, 0.80)
    ax.set_yticks([0.5, 0.6, 0.7, 0.8])
    ax.set_ylabel("Fleiss' $\\kappa$, full label")
    ax.legend(frameon=False, loc='upper left', handlelength=2.6, borderaxespad=0.2)
    tidy(ax)
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(out, 'fig_agreement.pdf'), metadata=NO_DATE)
    plt.close(fig)


def panel_title(ax, head, sub):
    ax.text(0, 1.33, head, transform=ax.transAxes, fontweight='bold', va='bottom')
    ax.text(0, 1.04, sub, transform=ax.transAxes, va='bottom', linespacing=1.05)


def draw_lines(ax, series):
    """One line per sample over T1, T2, T3."""
    for sample in ('dev', 'test'):
        st = STYLE[sample]
        ax.plot([1, 2, 3], series[sample], color=st['color'], linestyle=st['linestyle'],
                marker=st['marker'], markerfacecolor=st['markerfacecolor'], markersize=4.5,
                linewidth=1.3, markeredgewidth=0.9, label=st['label'], clip_on=False, zorder=3)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels([name for _, name in VERSIONS])
    ax.set_xlim(0.7, 3.3)
    tidy(ax)


def fig_outcomes(out):
    fig, axes = plt.subplots(1, 4, figsize=(6.3, 2.2))
    fig.subplots_adjust(left=0.085, right=0.995, top=0.73, bottom=0.27, wspace=0.42)
    confusions = [('Resolve', 'argument label vs.\nno extension', 'ext', 'ARG~none'),
                  ('Relocate', 'content word vs.\nstructural (falls)', 'dom', 'LEX-CONT~STRUCT'),
                  ('', 'content word vs.\nfunction word (rises)', 'dom', 'LEX-CONT~LEX-FUNC')]
    for ax, (head, sub, layer, pair) in zip(axes[:3], confusions):
        draw_lines(ax, {s: [confusion_pct(run, s, layer, pair) for run, _ in VERSIONS]
                        for s in ('dev', 'test')})
        ax.set_ylim(0, 6)
        ax.set_yticks([0, 2, 4, 6])
        panel_title(ax, head, sub)
    axes[0].set_ylabel('Confusion (% of\nmodel-pair comparisons)')

    ax = axes[3]
    draw_lines(ax, {s: modality_label_use(s) for s in ('dev', 'test')})
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 50, 100])
    ax.set_ylabel('% of annotations')
    panel_title(ax, 'Reveal', 'modal edits given the\nmodality label (rises)')

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=2, loc='lower center',
               bbox_to_anchor=(0.5, -0.01), handlelength=2.8, columnspacing=2.0)
    fig.savefig(os.path.join(out, 'fig_outcomes.pdf'), metadata=NO_DATE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='figures')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    use_times()
    fig_agreement(args.out)
    fig_outcomes(args.out)
    print('wrote fig_agreement.pdf and fig_outcomes.pdf to', args.out)


if __name__ == '__main__':
    main()
