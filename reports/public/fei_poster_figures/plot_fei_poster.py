"""Render poster-ready FEI figures from saved validation and test reports."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np


ROOT = next((parent for parent in Path(__file__).resolve().parents if (parent / "face_memory_system").is_dir()), Path(__file__).resolve().parents[2])
SOURCE = ROOT / "private_data/fei_original/reports"
INK, MUTED, GRID = "#152d3d", "#4f6776", "#dbe5eb"
KNOWN, UNKNOWN, FAIL, VALID = "#087b72", "#3e62a7", "#bd472e", "#768aa0"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": INK, "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.color": MUTED, "ytick.color": MUTED,
    "grid.color": GRID, "legend.frameon": False, "svg.fonttype": "path",
    "svg.hashsalt": "fei-poster-v1",
})


def canvas(section, title, subtitle, footer, *, width=10.5, height=6):
    fig = plt.figure(figsize=(width, height), facecolor="white")
    fig.text(.07, .941, section.upper(), color=KNOWN, size=11, weight="bold")
    fig.text(.07, .871, title, size=24, weight="bold")
    fig.text(.07, .816, subtitle, color=MUTED, size=11)
    fig.text(.07, .045, footer, color=MUTED, size=9)
    return fig


def chart_axis(fig, bounds=(.12, .18, .81, .55), *, grid="y"):
    ax = fig.add_axes(bounds)
    ax.set_axisbelow(True)
    ax.grid(axis=grid)
    return ax


def test_metrics(test):
    known = test["known_query_count"]
    unknown = test["unknown_query_count"]
    correct = round(test["known_top1_accuracy"] * known)
    false_accepts = round(test["unknown_fpir"] * unknown)
    fig = canvas(
        "01 / Test results", "Face identification on FEI",
        f'YuNet + SFace  |  {test["query_count"]:,} held-out image queries  |  Locked threshold {test["threshold"]:.5f}',
        "Source: FEI Face Database benchmark. Capture sessions were not documented.",
        height=5.1,
    )
    cards = [
        ("Known Top-1", f'{test["known_top1_accuracy"]:.1%}', f"{correct} / {known} known queries correct",
         "Capstone target: at least 80%", KNOWN),
        ("Macro F1", f'{test["macro_f1"]:.2%}', f'{len(test["per_class"])} equally weighted classes',
         "Includes the Unknown class", UNKNOWN),
        ("Unknown FPIR", f'{test["unknown_fpir"]:.0%}', f"{false_accepts} / {unknown} unknown queries accepted",
         "Observed on this test set", INK),
    ]
    for x, (label, value, detail, note, color) in zip((.07, .37, .67), cards):
        fig.add_artist(plt.Rectangle((x, .22), .27, .48, color="#f1f6f8", transform=fig.transFigure))
        fig.text(x+.018, .60, label, weight="bold", size=12)
        fig.text(x+.018, .43, value, color=color, weight="bold", size=37)
        fig.text(x+.018, .33, detail, size=10)
        fig.text(x+.018, .275, note, color=MUTED, size=9)
    return fig


def dataset_split(summary, validation, test):
    template_count = test["gallery_template_count"] + test["gallery_detection_or_encoding_failures"]
    known = [template_count, validation["known_query_count"], test["known_query_count"]]
    unknown = [0, validation["unknown_query_count"], test["unknown_query_count"]]
    fig = canvas(
        "02 / Protocol", "How the FEI images were split",
        f'{summary["dataset"]["images"]:,} original colour images  |  {summary["dataset"]["identities"]} people  |  Seed {summary["protocol"]["split_seed"]}',
        f'The same {test["gallery_person_count"]} enrolled identities span all three sets. Validation and test strangers are disjoint.',
    )
    ax = chart_axis(fig, (.15, .19, .76, .49), grid="x")
    labels = ["Gallery", "Validation", "Test"]
    ax.barh(labels, known, color=KNOWN, label="Enrolled identities", height=.55)
    ax.barh(labels, unknown, left=known, color=UNKNOWN, label="Unenrolled identities", height=.55)
    for y, (first, second) in enumerate(zip(known, unknown)):
        ax.text(first/2, y, str(first), color="white", ha="center", va="center", weight="bold")
        if second:
            ax.text(first+second/2, y, str(second), color="white", ha="center", va="center", weight="bold")
    ax.invert_yaxis()
    ax.set_xlabel("Images")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.025), ncols=2, borderaxespad=0)
    return fig


def test_outcomes(test):
    known = test["known_query_count"]
    unknown = test["unknown_query_count"]
    wrong = round(test["known_wrong_identity_rate"] * known)
    known_rejected = round(test["known_false_rejection_rate"] * known)
    unknown_accepted = round(test["unknown_fpir"] * unknown)
    table = [
        [known - wrong - known_rejected, wrong, known_rejected],
        [unknown - unknown_accepted, unknown_accepted, None],
    ]
    fig = canvas(
        "03 / Test outcomes", "What the system returned",
        "Outcome counts for enrolled and unenrolled people at the locked threshold",
        "A rejected known query counts as an error. An unknown query can be rejected without an embedding.",
    )
    columns = ["Correct decision", "Wrong name", "Known rejected"]
    descriptions = [["Correct identity", "Different enrolled identity", "No identity returned"],
                    ["No identity returned", "Assigned an enrolled identity", "Not applicable"]]
    for i, (row, label) in enumerate(zip(table, (f"KNOWN  (n={known})", f"UNKNOWN  (n={unknown})"))):
        y = .55 - i*.26
        fig.text(.07, y+.09, label, weight="bold", size=10)
        for j, count in enumerate(row):
            x = .23 + j*.24
            if not i:
                fig.text(x+.107, .715, columns[j], ha="center", weight="bold", size=11)
            color = KNOWN if j == 0 else FAIL
            fig.add_artist(plt.Rectangle((x, y-.055), .215, .2, color="#f1f6f8", transform=fig.transFigure))
            fig.text(x+.107, y+.047, "—" if count is None else str(count), ha="center", size=33,
                     color=color if count else MUTED, weight="bold")
            fig.text(x+.107, y-.01, descriptions[i][j], ha="center", size=8.5, color=MUTED)
    return fig


def score_histogram(test, key, title, xlabel, limit, limit_name, number, bins):
    groups = [
        [row[key] for row in test["predictions"]
         if (row["true_person_id"] is not None) == known and not row["face_detection_or_encoding_failure"]]
        for known in (True, False)
    ]
    dropped = test["detection_or_encoding_failures"]
    fig = canvas(
        f"{number} / Test scores", title,
        "Enrolled versus unenrolled queries with a valid embedding",
        f"Histograms are normalised within each group; {dropped} detection/encoding failures are excluded.",
    )
    ax = chart_axis(fig, (.12, .18, .81, .49))
    for values, label, color in zip(groups, ("Known", "Unknown"), (KNOWN, UNKNOWN)):
        counts, edges = np.histogram(values, bins=bins)
        ax.stairs(counts/len(values), edges, fill=True, alpha=.2, color=color)
        ax.stairs(counts/len(values), edges, color=color, linewidth=2, label=f"{label} (n={len(values)})")
    ax.axvline(limit, color=FAIL, linestyle="--", linewidth=1.8, label=f"{limit_name} {limit:.5g}")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_ylabel("Share of group per bin")
    ax.set_xlabel(xlabel)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.03), ncols=3, borderaxespad=0)
    return fig


def encoder_failures(validation, test):
    labels = ["Gallery", "Validation known", "Validation unknown", "Test known", "Test unknown"]
    gallery_failed = test["gallery_detection_or_encoding_failures"]
    groups = [(gallery_failed, test["gallery_template_count"] + gallery_failed)]
    for report in (validation, test):
        for known in (True, False):
            rows = [row for row in report["predictions"] if (row["true_person_id"] is not None) == known]
            groups.append((sum(row["face_detection_or_encoding_failure"] for row in rows), len(rows)))
    rates = [failed/count for failed, count in groups]
    fig = canvas(
        "06 / Error analysis", "Detection or encoding failures",
        "Failures as a share of each image group",
        "Counts cover failed face detection or embedding extraction; the gallery is counted once.",
    )
    ax = chart_axis(fig, (.24, .18, .68, .55), grid="x")
    ax.barh(labels, rates, color=[MUTED, VALID, VALID, FAIL, FAIL], height=.56)
    ax.set_xlim(0, max(rates)*1.55)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=1))
    for y, ((failed, count), rate) in enumerate(zip(groups, rates)):
        ax.text(rate+max(rates)*.04, y, f"{failed}/{count}  ({rate:.2%})", va="center", size=10)
    ax.invert_yaxis()
    ax.set_xlabel("Failure rate")
    return fig


def identity_recall(validation, test):
    def distribution(report):
        return Counter(round(item["recall"] * item["support"])
                       for label, item in report["per_class"].items() if label != "<unknown>")

    before, after = distribution(validation), distribution(test)
    possible = sorted(before.keys() | after.keys())
    x = np.arange(len(possible))
    support = sorted({item["support"] for report in (validation, test)
                      for label, item in report["per_class"].items() if label != "<unknown>"})
    if len(support) != 1:
        raise ValueError("Identity recall chart requires equal known-query support per identity")
    fig = canvas(
        "07 / Identity coverage", "How many queries were correct per person?",
        f'{test["gallery_person_count"]} enrolled identities  |  {support[0]} known queries per identity in each split',
        "Each bar counts people, with no identity labels shown.",
    )
    ax = chart_axis(fig, (.12, .18, .81, .49))
    for offset, split, color, counts in ((-.18, "Validation", VALID, before), (.18, "Test", KNOWN, after)):
        bars = ax.bar(x+offset, [counts[k] for k in possible], width=.31, color=color, label=split)
        ax.bar_label(bars, padding=4, weight="bold")
    ax.set_xticks(x, [f"{k} / {support[0]} correct" for k in possible])
    ax.set_ylim(0, 1.15*max(max(before.values()), max(after.values())))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Number of people")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.03), ncols=2, borderaxespad=0)
    return fig


def operating_curve(validation):
    cap = validation["validation_constraint_max_unknown_fpir"]
    frontier = sorted((p["unknown_fpir"], p["known_top1_accuracy"]) for p in validation["threshold_curve"]
                      if p["unknown_fpir"] <= cap)
    best_by_fpir = {}
    for fpir, accuracy in frontier:
        best_by_fpir[fpir] = accuracy
    fig = canvas(
        "08 / Validation only", "Accuracy versus false identification",
        f"Best Top-1 accuracy at each observed FPIR within the {cap:.0%} validation budget",
        "Each point uses the same minimum margin. The threshold was locked before evaluating test.",
    )
    ax = chart_axis(fig, (.12, .19, .79, .53))
    x, y = zip(*best_by_fpir.items())
    ax.plot(x, y, color=UNKNOWN, alpha=.8, linewidth=1.5, marker=".", markersize=5)
    chosen = (validation["unknown_fpir"], validation["known_top1_accuracy"])
    ax.scatter(*chosen, color=FAIL, s=72, edgecolor="white", zorder=4)
    ax.annotate(f"Locked threshold {validation['selected_threshold']:.5f}\n{chosen[1]:.1%} Top-1  |  {chosen[0]:.2%} FPIR",
                chosen, xytext=(.40, .23), textcoords="axes fraction", size=10,
                arrowprops={"arrowstyle": "->", "color": FAIL},
                bbox={"boxstyle": "round,pad=.35", "fc": "white", "ec": GRID})
    ax.set_xlim(-.001, cap+.001)
    ax.set_ylim(max(0, min(y)*.97), min(1.01, max(y)+.02))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=1))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_xlabel("Unknown false positive identification rate (FPIR)")
    ax.set_ylabel("Known Top-1 accuracy")
    return fig


def cpu_latency(validation, test):
    stats = [("mean_ms", "Mean"), ("median_ms", "Median"), ("p95_ms", "p95"), ("max_ms", "Maximum")]
    fig = canvas(
        "09 / CPU benchmark", "Image-to-match processing time",
        f'Local Linux x86-64 CPU  |  {test["query_count"]:,} image queries per split',
        "Timing covers image decoding, face encoding and matching. Live camera and audio playback are outside this measurement.",
    )
    ax = chart_axis(fig, (.12, .18, .81, .49))
    x = np.arange(len(stats))
    for offset, report, name, color in ((-.18, validation, "Validation", VALID), (.18, test, "Test", KNOWN)):
        bars = ax.bar(x+offset, [report["latency"][key] for key, _ in stats],
                      width=.32, label=name, color=color)
        ax.bar_label(bars, fmt="%.1f", padding=4, size=10)
    ax.set_xticks(x, [name for _, name in stats])
    ax.set_ylim(0, 1.15*max(report["latency"]["max_ms"] for report in (validation, test)))
    ax.set_ylabel("Milliseconds per query")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.03), ncols=2, borderaxespad=0)
    return fig


def decision_flow(test):
    fig = canvas(
        "10 / Model workflow", "From an image to an identity",
        "The same identification rule is applied to enrolled people and strangers",
        "Diagram of the still-image benchmark. The wearable adds live capture and audio playback.",
    )
    ax = fig.add_axes((.07, .15, .86, .59))
    ax.set_axis_off()

    def block(x, y, name, detail, color):
        ax.add_patch(plt.Rectangle((x-.1, y-.105), .2, .21, facecolor="#f1f6f8", edgecolor=GRID))
        ax.text(x, y+.032, name, ha="center", weight="bold", color=color, size=11)
        ax.text(x, y-.039, detail, ha="center", va="center", size=9, color=MUTED)

    def arrow(start, end):
        ax.annotate("", end, start, arrowprops={"arrowstyle": "->", "color": VALID, "lw": 1.5})

    nodes = [
        ("Input image", "Original colour image"),
        ("YuNet", "Detect one face\nand five landmarks"),
        ("SFace", "Align face and\nextract embedding"),
        ("Compare", "Rank enrolled people\nby cosine similarity"),
    ]
    for i, (name, detail) in enumerate(nodes):
        x = .105 + i*.255
        block(x, .73, name, detail, INK)
        if i:
            arrow((x-.155, .73), (x-.10, .73))
    arrow((.87, .625), (.87, .49))
    ax.text(.87, .45, f'Score ≥ {test["threshold"]:.5f} and margin ≥ {test["min_margin"]:.2f}?',
            ha="center", weight="bold", size=10, color=INK)
    arrow((.83, .42), (.62, .24))
    arrow((.9, .42), (.9, .24))
    ax.text(.76, .33, "Yes", color=KNOWN, size=9)
    ax.text(.92, .32, "No", color=FAIL, size=9)
    block(.62, .135, "Return identity", "Report the enrolled ID", KNOWN)
    block(.90, .135, "Reject", "Return no identity", FAIL)
    ax.text(.01, .20, "A detection or encoding failure\nalso returns no identity.", size=10, color=MUTED)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-report", type=Path, default=SOURCE / "validation.json")
    parser.add_argument("--test-report", type=Path, default=SOURCE / "test.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "reports/public/poster_report.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/public/fei_poster_figures")
    args = parser.parse_args()
    validation, test, summary = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (args.validation_report, args.test_report, args.summary)
    ]
    if (validation["split"], test["split"]) != ("validation", "test"):
        parser.error("Expected the FEI validation and test reports in that order")
    if (validation["selected_threshold"] != test["threshold"]
            or summary["model"]["threshold"] != test["threshold"]
            or validation["model_version"] != test["model_version"]
            or validation["min_margin"] != test["min_margin"]):
        parser.error("Reports do not share the same locked threshold and model settings")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "01_test_metrics": lambda: test_metrics(test),
        "02_dataset_split": lambda: dataset_split(summary, validation, test),
        "03_test_outcomes": lambda: test_outcomes(test),
        "04_similarity_distribution": lambda: score_histogram(
            test, "best_cosine_similarity", "Best similarity score by query group",
            "Best cosine similarity", test["threshold"], "Locked threshold", "04", np.linspace(0, 1, 41)),
        "05_margin_distribution": lambda: score_histogram(
            test, "best_second_margin", "Gap between the two best matches",
            "Best score minus second-best score", test["min_margin"], "Minimum margin", "05", np.linspace(0, .75, 39)),
        "06_detection_encoding_failures": lambda: encoder_failures(validation, test),
        "07_identity_recall": lambda: identity_recall(validation, test),
        "08_validation_operating_curve": lambda: operating_curve(validation),
        "09_cpu_latency": lambda: cpu_latency(validation, test),
        "10_decision_flow": lambda: decision_flow(test),
    }
    for name, draw in figures.items():
        fig = draw()
        fig.savefig(args.output_dir / f"{name}.png", dpi=300, facecolor="white")
        fig.savefig(args.output_dir / f"{name}.svg", metadata={"Date": None}, facecolor="white")
        plt.close(fig)
    print(f"Wrote {len(figures)} figures as PNG and SVG to {args.output_dir}")


if __name__ == "__main__":
    main()
