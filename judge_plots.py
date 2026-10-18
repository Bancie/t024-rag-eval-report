"""Matplotlib figures for the LLM-as-a-judge section.

Every count and rate comes from ``judge_summary`` and ``judge_rows``.
The rubric bounds (context 0–2, answer 1–5) are the only fixed numbers.
Figures use the same font, palette, and size as the recall@k plots.
"""

from __future__ import annotations

TYPE_ORDER = ("factual", "multi-section", "edge-case", "unanswerable")
ANSWERABLE_TYPES = ("factual", "multi-section", "edge-case")
FIGSIZE = (11.2, 6.4)
SCORE_COLORS = {0: "#F44336", 1: "#FF9800", 2: "#4CAF50"}
SERIES_COLORS = ("#2196F3", "#FF9800", "#9C27B0", "#4CAF50")

MISSING_JUDGE_FILES = (
    "**Thiếu file.** Phần này đọc `report/results/judge/judge_summary.json` và "
    "`judge_results.jsonl`. Chưa có kết quả judge, nên chưa có context relevance, "
    "answer relevance, hay tỉ lệ từ chối."
)


class JudgePlots:
    def __init__(self, figures=None, captions=None, warning=None, data=None):
        self.figures = list(figures or [])
        self.captions = list(captions or [])
        self.warning = warning
        self.data = dict(data or {})


def fmt4(value) -> str:
    if value is None or isinstance(value, bool):
        return "—"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "—"


def _ready(summary, rows) -> bool:
    return isinstance(summary, dict) and isinstance(rows, list)


def _score(value, allowed: set[int]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value not in allowed:
        return None
    return value


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def context_counts(rows: list) -> dict[str, dict[int, int]]:
    counts = {name: {0: 0, 1: 0, 2: 0} for name in TYPE_ORDER}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("type")
        if name not in counts:
            continue
        chunks = row.get("chunks")
        if not isinstance(chunks, list):
            continue
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            block = chunk.get("context_relevance")
            if not isinstance(block, dict):
                continue
            score = _score(block.get("score"), {0, 1, 2})
            if score is None:
                continue
            counts[name][score] += 1
    return counts


def answer_hist(rows: list) -> dict[int, int]:
    hist = {score: 0 for score in range(1, 6)}
    for row in rows:
        if not isinstance(row, dict):
            continue
        block = row.get("answer_relevance")
        if not isinstance(block, dict):
            continue
        score = _score(block.get("score"), {1, 2, 3, 4, 5})
        if score is None:
            continue
        hist[score] += 1
    return hist


def _block_rate(block: dict, rate_key: str, num_key: str, den_key: str) -> float | None:
    rate = _number(block.get(rate_key))
    if rate is not None:
        return rate
    num = _int(block.get(num_key))
    den = _int(block.get(den_key))
    if num is None or den is None or den == 0:
        return None
    return num / den


def _mean_rows(rows: list, name: str) -> tuple[float | None, int]:
    scores = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != name:
            continue
        block = row.get("answer_relevance")
        if not isinstance(block, dict):
            continue
        score = _score(block.get("score"), {1, 2, 3, 4, 5})
        if score is None:
            continue
        scores.append(score)
    if not scores:
        return None, 0
    return sum(scores) / len(scores), len(scores)


def _answer_means(summary: dict, rows: list) -> list[dict]:
    by_type = summary.get("by_type") if isinstance(summary.get("by_type"), dict) else {}
    items = []
    for name in TYPE_ORDER:
        block = by_type.get(name) if isinstance(by_type.get(name), dict) else {}
        fallback_mean, fallback_n = _mean_rows(rows, name)
        n = _int(block.get("n"))
        if n is None:
            n = fallback_n
        mean = _number(block.get("answer_relevance_mean"))
        if mean is None:
            mean = fallback_mean
        items.append({"type": name, "mean": mean, "n": n})
    return items


def _refusal_bars(summary: dict, rows: list) -> list[dict]:
    refusal = summary.get("refusal") if isinstance(summary.get("refusal"), dict) else {}
    by_type = summary.get("by_type") if isinstance(summary.get("by_type"), dict) else {}
    bars = []
    correct = _block_rate(refusal, "correct_refusal_rate", "n_correct_refusal", "n_unanswerable")
    n_correct = _int(refusal.get("n_correct_refusal"))
    n_unanswerable = _int(refusal.get("n_unanswerable"))
    if n_unanswerable is None or n_correct is None:
        unanswerable_rows = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("type") == "unanswerable"
        ]
        n_unanswerable = len(unanswerable_rows)
        n_correct = sum(
            1
            for row in unanswerable_rows
            if isinstance(row.get("refusal"), dict) and row["refusal"].get("refused") is True
        )
        if correct is None and n_unanswerable:
            correct = n_correct / n_unanswerable
    bars.append(
        {
            "type": "unanswerable",
            "kind": "correct",
            "rate": correct,
            "n_refused": n_correct,
            "n": n_unanswerable,
        }
    )
    for name in ANSWERABLE_TYPES:
        block = by_type.get(name) if isinstance(by_type.get(name), dict) else {}
        rate = _block_rate(block, "refusal_rate", "n_refused", "n")
        n_refused = _int(block.get("n_refused"))
        n = _int(block.get("n"))
        if n is None or n_refused is None:
            typed = [row for row in rows if isinstance(row, dict) and row.get("type") == name]
            n = len(typed)
            n_refused = sum(
                1
                for row in typed
                if isinstance(row.get("refusal"), dict) and row["refusal"].get("refused") is True
            )
            if rate is None and n:
                rate = n_refused / n
        bars.append(
            {
                "type": name,
                "kind": "false",
                "rate": rate,
                "n_refused": n_refused,
                "n": n,
            }
        )
    return bars


def _matrix(summary: dict, rows: list) -> dict:
    comparison = (
        summary.get("recall_comparison")
        if isinstance(summary.get("recall_comparison"), dict)
        else {}
    )
    keys = (
        "both_positive",
        "span_hit_judge_not_strict",
        "span_miss_judge_strict",
        "both_negative",
        "n_answerable_scored",
    )
    if all(_int(comparison.get(key)) is not None for key in keys):
        return {key: comparison.get(key) for key in keys}
    both_positive = span_only = judge_only = both_negative = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("type") == "unanswerable":
            continue
        chunks = row.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            continue
        span_hit = any(bool(chunk.get("gold_hit")) for chunk in chunks if isinstance(chunk, dict))
        scores = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            block = chunk.get("context_relevance")
            if isinstance(block, dict):
                score = _score(block.get("score"), {0, 1, 2})
                if score is not None:
                    scores.append(score)
        if not scores:
            continue
        strict = max(scores) >= 2
        if span_hit and strict:
            both_positive += 1
        elif span_hit:
            span_only += 1
        elif strict:
            judge_only += 1
        else:
            both_negative += 1
    n = both_positive + span_only + judge_only + both_negative
    return {
        "both_positive": both_positive,
        "span_hit_judge_not_strict": span_only,
        "span_miss_judge_strict": judge_only,
        "both_negative": both_negative,
        "n_answerable_scored": n,
    }


def _agreement(summary: dict, rows: list) -> list[dict]:
    agreement = summary.get("agreement") if isinstance(summary.get("agreement"), dict) else {}
    specs = (
        ("context relevance", "context_score_exact_rate", "context_score_exact_n", "n_chunks"),
        ("answer relevance", "answer_score_exact_rate", "answer_score_exact_n", "n_scored"),
        ("refusal", "refusal_agreement_rate", "refusal_agreement_n", "n_scored"),
    )
    if all(_number(agreement.get(rate_key)) is not None for _label, rate_key, _hit, _total in specs):
        items = []
        for label, rate_key, hit_key, total_key in specs:
            items.append(
                {
                    "label": label,
                    "rate": agreement.get(rate_key),
                    "hit": agreement.get(hit_key),
                    "total": agreement.get(total_key),
                }
            )
        return items
    ctx_hit = ctx_n = ans_hit = ref_hit = 0
    scored = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunks = row.get("chunks") if isinstance(row.get("chunks"), list) else []
        answer = row.get("answer_relevance") if isinstance(row.get("answer_relevance"), dict) else None
        answer2 = row.get("answer_relevance_run2") if isinstance(row.get("answer_relevance_run2"), dict) else None
        refusal = row.get("refusal") if isinstance(row.get("refusal"), dict) else None
        refusal2 = row.get("refusal_run2") if isinstance(row.get("refusal_run2"), dict) else None
        if answer is None or answer2 is None or refusal is None or refusal2 is None:
            continue
        scored += 1
        if answer.get("score") == answer2.get("score"):
            ans_hit += 1
        if refusal.get("refused") == refusal2.get("refused"):
            ref_hit += 1
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            first = chunk.get("context_relevance") if isinstance(chunk.get("context_relevance"), dict) else {}
            second = chunk.get("context_relevance_run2") if isinstance(chunk.get("context_relevance_run2"), dict) else {}
            ctx_n += 1
            if first.get("score") == second.get("score"):
                ctx_hit += 1
    def _rate(hit: int, total: int) -> float | None:
        if total == 0:
            return None
        return hit / total

    return [
        {"label": "context relevance", "rate": _rate(ctx_hit, ctx_n), "hit": ctx_hit, "total": ctx_n},
        {"label": "answer relevance", "rate": _rate(ans_hit, scored), "hit": ans_hit, "total": scored},
        {"label": "refusal", "rate": _rate(ref_hit, scored), "hit": ref_hit, "total": scored},
    ]


def _pct(rate) -> str:
    value = _number(rate)
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _fraction(num, den) -> str:
    if num is None or den is None:
        return "—"
    return f"{num}/{den}"


def _best(items: list[tuple[str, float]]) -> list[str]:
    if not items:
        return []
    top = max(value for _name, value in items)
    return [name for name, value in items if value == top]


def _caption_context(summary: dict, counts: dict[str, dict[int, int]]) -> str:
    overall = summary.get("overall") if isinstance(summary.get("overall"), dict) else {}
    by_type = summary.get("by_type") if isinstance(summary.get("by_type"), dict) else {}
    n0 = sum(counts[name][0] for name in TYPE_ORDER)
    n1 = sum(counts[name][1] for name in TYPE_ORDER)
    n2 = sum(counts[name][2] for name in TYPE_ORDER)
    n_chunks = n0 + n1 + n2
    stored_chunks = overall.get("n_chunks")
    chunk_bit = str(n_chunks)
    if stored_chunks is not None:
        chunk_bit = str(stored_chunks)
    unanswerable = counts["unanswerable"]
    unanswerable_n = sum(unanswerable.values())
    unanswerable_block = by_type.get("unanswerable") if isinstance(by_type.get("unanswerable"), dict) else {}
    means = []
    for name in TYPE_ORDER:
        block = by_type.get(name) if isinstance(by_type.get(name), dict) else {}
        mean = _number(block.get("context_relevance_mean"))
        if mean is not None:
            means.append((name, mean))
    best = _best(means)
    best_bit = ""
    if best:
        best_mean = next(value for name, value in means if name == best[0])
        best_bit = (
            " Trung bình context relevance cao nhất là "
            + ", ".join(f"`{name}`" for name in best)
            + " ("
            + fmt4(best_mean)
            + ")."
        )
    return (
        f"Trên {chunk_bit} chunk, context relevance điểm 0 là {n0}, điểm 1 là {n1} và điểm 2 là {n2}. "
        f"Nhóm unanswerable có {unanswerable[0]} chunk điểm 0, {unanswerable[1]} điểm 1 và {unanswerable[2]} điểm 2"
        f" (trên {unanswerable_n} chunk của nhóm), trung bình {fmt4(unanswerable_block.get('context_relevance_mean'))}."
        f"{best_bit}"
    )


def _caption_answer(summary: dict, means: list[dict], hist: dict[int, int]) -> str:
    overall = summary.get("overall") if isinstance(summary.get("overall"), dict) else {}
    parts = []
    for item in means:
        if item["mean"] is None or not item["n"]:
            parts.append(f"`{item['type']}` không có câu được chấm")
            continue
        parts.append(f"`{item['type']}` {fmt4(item['mean'])} (n={item['n']})")
    n_scored = overall.get("n_scored")
    if n_scored is None:
        n_scored = sum(hist.values())
    low = hist[1] + hist[2] + hist[3]
    return (
        "Answer relevance trung bình theo type: "
        + "; ".join(parts)
        + f". Trên {n_scored} câu, điểm 5 có {hist[5]} câu, điểm 4 có {hist[4]} câu, "
        + f"và điểm 1–3 cộng lại {low} câu (điểm 1: {hist[1]}, điểm 2: {hist[2]}, điểm 3: {hist[3]})."
    )


def _caption_refusal(summary: dict, bars: list[dict]) -> str:
    refusal = summary.get("refusal") if isinstance(summary.get("refusal"), dict) else {}
    correct = _block_rate(refusal, "correct_refusal_rate", "n_correct_refusal", "n_unanswerable")
    false = _block_rate(refusal, "false_refusal_rate", "n_false_refusal", "n_answerable")
    n_correct = refusal.get("n_correct_refusal")
    n_unanswerable = refusal.get("n_unanswerable")
    n_false = refusal.get("n_false_refusal")
    n_answerable = refusal.get("n_answerable")
    false_bars = [bar for bar in bars if bar["kind"] == "false" and _number(bar.get("rate")) is not None]
    best_bit = ""
    if false_bars:
        top = max(_number(bar["rate"]) or 0 for bar in false_bars)
        winners = [bar for bar in false_bars if _number(bar["rate"]) == top]
        bits = [
            f"`{bar['type']}` {_pct(bar['rate'])} ({_fraction(bar['n_refused'], bar['n'])})"
            for bar in winners
        ]
        best_bit = " Trong các type answerable, false refusal rate cao nhất là " + " và ".join(bits) + "."
    return (
        f"Correct refusal rate của nhóm unanswerable là {fmt4(correct)} "
        f"({_fraction(n_correct, n_unanswerable)}). "
        f"False refusal rate trên câu answerable là {fmt4(false)} "
        f"({_fraction(n_false, n_answerable)})."
        f"{best_bit}"
    )


def _caption_matrix(matrix: dict) -> str:
    n = matrix.get("n_answerable_scored")
    return (
        f"Trên {n} câu answerable, {matrix.get('both_positive')} câu vừa span hit vừa judge strict hit, "
        f"và {matrix.get('both_negative')} câu vừa span miss vừa không có chunk điểm 2. "
        f"{matrix.get('span_hit_judge_not_strict')} câu có gold span trong top-k nhưng không có chunk điểm 2; "
        f"{matrix.get('span_miss_judge_strict')} câu không có gold span nhưng có ít nhất một chunk điểm 2."
    )


def _caption_agreement(summary: dict, items: list[dict]) -> str:
    agreement = summary.get("agreement") if isinstance(summary.get("agreement"), dict) else {}
    by_label = {item["label"]: item for item in items}
    context = by_label.get("context relevance") or {}
    answer = by_label.get("answer relevance") or {}
    refusal = by_label.get("refusal") or {}
    within = agreement.get("answer_score_within_1_rate")
    within_n = agreement.get("answer_score_within_1_n")
    within_bit = ""
    if within is not None:
        within_bit = (
            f" Answer score lệch tối đa 1 điểm trên {fmt4(within)}"
            f" câu ({_fraction(within_n, answer.get('total'))})."
        )
    return (
        f"Hai lần chấm khớp context relevance {fmt4(context.get('rate'))} "
        f"({_fraction(context.get('hit'), context.get('total'))} chunk), "
        f"answer relevance {fmt4(answer.get('rate'))} "
        f"({_fraction(answer.get('hit'), answer.get('total'))} câu), "
        f"và refusal {fmt4(refusal.get('rate'))} "
        f"({_fraction(refusal.get('hit'), refusal.get('total'))} câu)."
        f"{within_bit}"
    )


def _label_bars(ax, bars, labels) -> None:
    for bar, label in zip(bars, labels):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)


def _finish(fig, *, legend_outside: bool) -> None:
    if legend_outside:
        fig.tight_layout(rect=(0, 0, 0.80, 1))
    else:
        fig.tight_layout()


def _empty_axes(ax, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])


def _figure_context(plt, counts: dict[str, dict[int, int]]):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    totals = [sum(counts[name].values()) for name in TYPE_ORDER]
    if not any(totals):
        _style(ax, "Phân bố context relevance theo type", "type câu hỏi", "Số chunk")
        _empty_axes(ax, "Không có chunk được chấm.")
        _finish(fig, legend_outside=False)
        return fig
    bottoms = [0 for _ in TYPE_ORDER]
    x = list(range(len(TYPE_ORDER)))
    for score in (0, 1, 2):
        heights = [counts[name][score] for name in TYPE_ORDER]
        bars = ax.bar(
            x,
            heights,
            bottom=bottoms,
            color=SCORE_COLORS[score],
            edgecolor="white",
            linewidth=1.5,
            width=0.6,
            label=f"điểm {score}",
        )
        for index, (height, bottom) in enumerate(zip(heights, bottoms)):
            if height <= 0:
                continue
            ink = "black" if score == 1 else "white"
            ax.text(
                index,
                bottom + height / 2,
                str(height),
                ha="center",
                va="center",
                fontsize=9,
                color=ink,
            )
        bottoms = [bottom + height for bottom, height in zip(bottoms, heights)]
    for index, total in enumerate(bottoms):
        ax.text(index, total, str(int(total)), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(list(TYPE_ORDER))
    _style(ax, "Phân bố context relevance theo type", "type câu hỏi", "Số chunk")
    peak = max(bottoms) if bottoms else 1
    ax.set_ylim(0, peak * 1.14 if peak else 1)
    ax.legend(
        title="context relevance",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=8,
        framealpha=0.95,
    )
    _finish(fig, legend_outside=True)
    return fig


def _figure_answer(plt, means: list[dict], hist: dict[int, int]):
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE)
    ax_mean, ax_hist = axes
    x = list(range(len(means)))
    heights = [0 if item["mean"] is None or not item["n"] else float(item["mean"]) for item in means]
    bars = ax_mean.bar(
        x,
        heights,
        color="#2196F3",
        edgecolor="white",
        linewidth=1.5,
        width=0.6,
    )
    labels = []
    for item in means:
        if item["mean"] is None or not item["n"]:
            labels.append(f"—\nn={item['n'] or 0}")
        else:
            labels.append(f"{fmt4(item['mean'])}\nn={item['n']}")
    _label_bars(ax_mean, bars, labels)
    ax_mean.set_xticks(x)
    ax_mean.set_xticklabels([item["type"] for item in means])
    _style(
        ax_mean,
        "Answer relevance trung bình theo type",
        "type câu hỏi",
        "Answer relevance trung bình (1–5)",
    )
    ax_mean.set_ylim(0, 6.8)
    scores = list(range(1, 6))
    hist_bars = ax_hist.bar(
        scores,
        [hist[score] for score in scores],
        color="#2196F3",
        edgecolor="white",
        linewidth=1.5,
        width=0.6,
    )
    _label_bars(ax_hist, hist_bars, [str(hist[score]) for score in scores])
    ax_hist.set_xticks(scores)
    _style(ax_hist, "Phân bố điểm answer relevance", "điểm answer relevance (1–5)", "Số câu")
    peak = max(hist.values()) if hist else 1
    ax_hist.set_ylim(0, (peak * 1.16) if peak else 1)
    _finish(fig, legend_outside=False)
    return fig


def _figure_refusal(plt, bars: list[dict]):
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = list(range(len(bars)))
    heights = [0 if bar["rate"] is None else float(bar["rate"]) * 100 for bar in bars]
    colors = ["#4CAF50" if bar["kind"] == "correct" else "#F44336" for bar in bars]
    drawn = ax.bar(x, heights, color=colors, edgecolor="white", linewidth=1.5, width=0.6)
    labels = []
    tick_labels = []
    for bar in bars:
        labels.append(f"{_pct(bar['rate'])}\n{_fraction(bar['n_refused'], bar['n'])}")
        kind = "correct refusal" if bar["kind"] == "correct" else "false refusal"
        tick_labels.append(f"{bar['type']}\n({kind})")
    _label_bars(ax, drawn, labels)
    ax.set_xticks(x)
    ax.set_xticklabels(tick_labels)
    _style(
        ax,
        "Correct refusal rate và false refusal rate theo type",
        "type câu hỏi",
        "Tỉ lệ (%)",
    )
    peak = max(heights) if heights else 1
    ax.set_ylim(0, max(120, peak * 1.28))
    ax.legend(
        handles=[
            Patch(facecolor="#4CAF50", edgecolor="white", label="correct refusal rate (unanswerable)"),
            Patch(facecolor="#F44336", edgecolor="white", label="false refusal rate (type answerable)"),
        ],
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=8,
        framealpha=0.95,
    )
    _finish(fig, legend_outside=True)
    return fig


def _figure_matrix(plt, matrix: dict):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    grid = [
        [matrix["both_positive"], matrix["span_hit_judge_not_strict"]],
        [matrix["span_miss_judge_strict"], matrix["both_negative"]],
    ]
    image = ax.imshow(grid, cmap="Blues", aspect="auto")
    image.set_clim(0, max(max(row) for row in grid) or 1)
    peak = max(max(row) for row in grid) or 1
    for row_index, row in enumerate(grid):
        for col_index, value in enumerate(row):
            ink = "white" if value >= peak / 2 else "black"
            ax.text(col_index, row_index, str(value), ha="center", va="center", fontsize=20, color=ink)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["có", "không"])
    ax.set_yticklabels(["có", "không"])
    ax.set_xticks([-0.5, 0.5, 1.5], minor=True)
    ax.set_yticks([-0.5, 0.5, 1.5], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    n = matrix.get("n_answerable_scored")
    ax.set_title(f"Span hit và judge strict hit (n={n} câu answerable)")
    ax.set_xlabel("judge strict hit (ít nhất một chunk điểm 2)")
    ax.set_ylabel("span hit (gold span trong top-k)")
    ax.tick_params(length=0)
    fig.tight_layout()
    return fig


def _figure_agreement(plt, items: list[dict]):
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = list(range(len(items)))
    heights = [0 if item["rate"] is None else float(item["rate"]) * 100 for item in items]
    colors = [SERIES_COLORS[index % len(SERIES_COLORS)] for index in x]
    bars = ax.bar(x, heights, color=colors, edgecolor="white", linewidth=1.5, width=0.6)
    for index, (bar, item) in enumerate(zip(bars, items)):
        label = f"{_pct(item['rate'])}\n{_fraction(item['hit'], item['total'])}"
        ink = "black" if colors[index] == "#FF9800" else "white"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2 if bar.get_height() else 0,
            label,
            ha="center",
            va="center",
            fontsize=8,
            color=ink,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([item["label"] for item in items])
    _style(ax, "Độ khớp giữa 2 lần chấm judge", "chỉ số", "Tỉ lệ khớp (%)")
    ax.set_ylim(0, 115)
    ax.legend(
        handles=[
            Patch(facecolor=color, edgecolor="white", label=item["label"])
            for color, item in zip(colors, items)
        ],
        title="khớp chính xác lần 1 và lần 2",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=8,
        framealpha=0.95,
    )
    _finish(fig, legend_outside=True)
    return fig


def render_judge_plots(summary, rows) -> JudgePlots:
    """Build the five judge figures. Missing JSON returns a warning and no figures."""

    if not _ready(summary, rows):
        return JudgePlots(warning=MISSING_JUDGE_FILES)

    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.close("all")
    counts = context_counts(rows)
    hist = answer_hist(rows)
    means = _answer_means(summary, rows)
    bars = _refusal_bars(summary, rows)
    matrix = _matrix(summary, rows)
    agreement = _agreement(summary, rows)
    figures = [
        _figure_context(plt, counts),
        _figure_answer(plt, means, hist),
        _figure_refusal(plt, bars),
        _figure_matrix(plt, matrix),
        _figure_agreement(plt, agreement),
    ]
    captions = [
        _caption_context(summary, counts),
        _caption_answer(summary, means, hist),
        _caption_refusal(summary, bars),
        _caption_matrix(matrix),
        _caption_agreement(summary, agreement),
    ]
    return JudgePlots(
        figures=figures,
        captions=captions,
        data={
            "context_counts": counts,
            "answer_means": means,
            "answer_hist": hist,
            "refusal_bars": bars,
            "matrix": matrix,
            "agreement": agreement,
        },
    )
