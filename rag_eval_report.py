# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.16",
#     "matplotlib>=3.8",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import html as html_lib
    import json
    import re
    import textwrap
    from pathlib import Path

    import marimo as mo

    def resolve_report_dir():
        """Directory of this notebook. Prefer __file__; fall back to mo.notebook_dir()."""

        try:
            here = Path(__file__).resolve().parent
        except NameError:
            notebook = mo.notebook_dir()
            here = Path(notebook) if notebook is not None else Path.cwd()
        data_probe = here / "data" / "testset.jsonl"
        results_probe = here / "results"
        if data_probe.is_file() or results_probe.is_dir():
            return here
        notebook = mo.notebook_dir()
        if notebook is not None:
            fallback = Path(notebook)
            if (fallback / "data" / "testset.jsonl").is_file() or (fallback / "results").is_dir():
                return fallback
        return here

    REPORT_DIR = resolve_report_dir()
    DATA_DIR = REPORT_DIR / "data"
    RESULTS_DIR = REPORT_DIR / "results"

    def rel_path(path):
        root = REPORT_DIR
        try:
            return str(Path(path).resolve().relative_to(root.resolve()))
        except ValueError:
            return str(path)

    def load_json(path):
        if not path.is_file():
            return None, "thiếu file"
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except json.JSONDecodeError as exc:
            return None, "JSON không hợp lệ: " + exc.msg
        except OSError as exc:
            return None, "không đọc được: " + str(exc)

    def load_jsonl(path):
        if not path.is_file():
            return None, "thiếu file"
        rows = []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, "không đọc được: " + str(exc)
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                return None, "JSON không hợp lệ ở dòng " + str(number) + ": " + exc.msg
        return rows, None

    def load_text(path):
        if not path.is_file():
            return None, "thiếu file"
        try:
            return path.read_text(encoding="utf-8"), None
        except OSError as exc:
            return None, "không đọc được: " + str(exc)

    def _record(notes, path, error):
        if error:
            notes.append("`" + rel_path(path) + "` (" + error + ").")

    load_notes = []
    testset, _testset_error = load_jsonl(DATA_DIR / "testset.jsonl")
    _record(load_notes, DATA_DIR / "testset.jsonl", _testset_error)
    review_report, _review_error = load_json(DATA_DIR / "review_report.json")
    _record(load_notes, DATA_DIR / "review_report.json", _review_error)
    generation_report, _generation_error = load_json(DATA_DIR / "generation_report.json")
    _record(load_notes, DATA_DIR / "generation_report.json", _generation_error)
    manifest_text, _manifest_error = load_text(RESULTS_DIR / "MANIFEST.md")
    _record(load_notes, RESULTS_DIR / "MANIFEST.md", _manifest_error)

    summaries = {}
    run_rows = {}
    if not RESULTS_DIR.is_dir():
        load_notes.append("`report/results/` (thiếu thư mục).")
    else:
        _summary_paths = sorted(RESULTS_DIR.glob("*.summary.json"))
        if not _summary_paths:
            load_notes.append("`report/results/*.summary.json` (không có file summary).")
        for _summary_path in _summary_paths:
            _summary, _summary_err = load_json(_summary_path)
            if _summary_err or not isinstance(_summary, dict):
                _record(load_notes, _summary_path, _summary_err or "không phải JSON object")
                continue
            _chunker = str(_summary.get("chunker") or _summary.get("run_id") or _summary_path.stem)
            if _chunker in summaries:
                load_notes.append(
                    "`" + rel_path(_summary_path) + "` (chunker trùng `" + _chunker + "`, giữ file đầu tiên)."
                )
                continue
            _run_id = str(_summary.get("run_id") or _summary_path.name.replace(".summary.json", ""))
            _jsonl_path = RESULTS_DIR / (_run_id + ".jsonl")
            _rows, _rows_err = load_jsonl(_jsonl_path)
            if _rows_err:
                _record(load_notes, _jsonl_path, _rows_err)
                _rows = None
            summaries[_chunker] = _summary
            run_rows[_chunker] = _rows

    TOP10_DIR = RESULTS_DIR / "top10"
    recall_curve, _curve_error = load_json(TOP10_DIR / "recall_curve.json")
    _record(load_notes, TOP10_DIR / "recall_curve.json", _curve_error)
    top10_rows = {}
    for _chunker in ("section", "window", "sentence"):
        _top_path = TOP10_DIR / (_chunker + "-top10.jsonl")
        _top_rows, _top_err = load_jsonl(_top_path)
        if _top_err:
            _record(load_notes, _top_path, _top_err)
            top10_rows[_chunker] = None
            continue
        _normalized = []
        for _row in _top_rows:
            _item = dict(_row)
            _item["scored"] = True
            if not _item.get("status"):
                _item["status"] = "accepted"
            _normalized.append(_item)
        top10_rows[_chunker] = _normalized

    def escape_text(value):
        return html_lib.escape("" if value is None else str(value))

    def fmt4(value):
        if value is None:
            return "—"
        return f"{float(value):.4f}"

    def shorten(text, limit=200):
        compact = " ".join(str(text or "").split())
        if not compact:
            return "—"
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."

    def rank_text(rank):
        if rank is None:
            return "null"
        return str(rank)

    def is_hit(rank, k):
        return isinstance(rank, int) and not isinstance(rank, bool) and rank >= 1 and rank <= k

    def ordered(keys, preferred):
        present = []
        seen = set()
        for key in keys:
            if key not in seen:
                present.append(key)
                seen.add(key)
        head = [key for key in preferred if key in seen]
        tail = sorted((key for key in present if key not in head), key=lambda item: str(item))
        return head + tail

    def md_table(headers, rows):
        def cell(value):
            text = "—" if value is None else str(value)
            return text.replace("|", "\\|").replace("\n", " ")

        lines = [
            "| " + " | ".join(str(header) for header in headers) + " |",
            "| " + " | ".join("---" for _header in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(cell(value) for value in row) + " |")
        return "\n".join(lines)

    def md_fill(template, **kwargs):
        text = textwrap.dedent(template).strip()

        def replace(match):
            key = match.group(1)
            if key not in kwargs:
                return match.group(0)
            value = kwargs[key]
            if value is None:
                return "—"
            return str(value)

        text = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, text)
        return mo.md(text)

    def show_table(rows, label=""):
        if not rows:
            return mo.md("_Không có dòng nào._")
        wrap = [
            key
            for key in (
                "question",
                "gold_span",
                "reference_answer",
                "reviewer_note",
                "note",
                "section",
                "flag",
            )
            if key in rows[0]
        ]
        return mo.ui.table(
            rows,
            pagination=False,
            selection=None,
            show_column_summaries=False,
            label=label,
            wrapped_columns=wrap or None,
        )

    def kappa_band(value):
        if value is None:
            return "không xác định"
        if value < 0:
            return "kém (thấp hơn mức ngẫu nhiên)"
        if value <= 0.20:
            return "nhẹ"
        if value <= 0.40:
            return "tạm"
        if value <= 0.60:
            return "vừa"
        if value <= 0.80:
            return "đáng kể"
        return "gần như hoàn hảo"

    def same_metric(got, expected):
        if got is None or expected is None:
            return got is None and expected is None
        return round(float(got), 4) == round(float(expected), 4)

    def scored_rows(rows):
        return [row for row in rows if row.get("scored")]

    def recall_of(rows, k):
        scored = scored_rows(rows)
        if not scored:
            return None
        hits = sum(1 for row in scored if is_hit(row.get("first_hit_rank"), k))
        return hits / len(scored)

    def mrr_of(rows):
        scored = scored_rows(rows)
        if not scored:
            return None
        total = 0.0
        for row in scored:
            rank = row.get("first_hit_rank")
            if isinstance(rank, int) and not isinstance(rank, bool) and rank >= 1:
                total += 1.0 / rank
        return total / len(scored)

    def group_by(rows, key):
        grouped = {}
        for row in rows:
            grouped.setdefault(row.get(key), []).append(row)
        return grouped

    def bar_chart(items, title):
        parts = [
            "<div style='max-width:640px;font-family:ui-sans-serif,system-ui,sans-serif;font-size:14px;margin:8px 0 16px'>",
            "<div style='font-weight:600;margin-bottom:6px'>" + escape_text(title) + "</div>",
        ]
        for label, value, color in items:
            safe_color = color if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color) else "#2563eb"
            if value is None:
                width = 0.0
                shown = "—"
            else:
                width = max(0.0, min(100.0, float(value) * 100.0))
                shown = f"{float(value):.4f}"
            parts.append(
                "<div style='display:flex;align-items:center;gap:8px;margin:4px 0'>"
                + "<div style='width:200px'>"
                + escape_text(label)
                + "</div>"
                + "<div style='flex:1;background:#e5e7eb;height:14px;border-radius:4px;overflow:hidden'>"
                + f"<div style='width:{width:.2f}%;background:{safe_color};height:14px'></div>"
                + "</div>"
                + "<div style='width:72px;text-align:right'>"
                + shown
                + "</div></div>"
            )
        parts.append("</div>")
        return mo.Html("".join(parts))

    def build_manifest(text):
        if not text:
            return {"ok": False, "date": None, "date_detail": None, "embedding": None, "embedding_detail": None}
        date_detail = None
        embedding_detail = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- Date:"):
                date_detail = stripped.split("Date:", 1)[1].strip()
            elif stripped.startswith("- Embedding:"):
                embedding_detail = stripped.split("Embedding:", 1)[1].strip()
        date = date_detail.split(" ", 1)[0] if date_detail else None
        embedding = embedding_detail.split(" via ", 1)[0].strip() if embedding_detail else None
        return {
            "ok": True,
            "date": date,
            "date_detail": date_detail,
            "embedding": embedding,
            "embedding_detail": embedding_detail,
        }

    def build_generation(report):
        if not isinstance(report, dict):
            return {"ok": False}
        note = str(report.get("ragas_note") or "")
        parts = [part.strip() for part in re.split(r"(?<=[.])\s+", note.strip()) if part.strip()]
        reason = ""
        for part in parts:
            if "failed" in part.lower() or "connectionerror" in part.lower():
                reason = part
                break
        if not reason:
            for part in parts:
                if "prompt generator" in part.lower():
                    reason = part
                    break
        if not reason and parts:
            reason = parts[0]
        return {
            "ok": True,
            "backend": report.get("backend"),
            "written": report.get("written"),
            "span_check_failed": report.get("span_check_failed"),
            "repaired": report.get("repaired"),
            "per_doc_written": report.get("per_doc_written") or {},
            "reason": reason,
            "note": note,
        }

    def build_dataset(testset_rows, review, summary_map):
        if not testset_rows:
            return {"ok": False, "missing": "data/testset.jsonl"}
        status_order = ["accepted", "rejected", "candidate"]
        type_order = ["factual", "edge-case", "multi-section", "unanswerable"]
        doc_order = ["nuimages", "mapillary_vistas", "cityscapes"]
        by_status = {}
        by_doc = {}
        by_type = {}
        status_type = {}
        status_doc = {}
        for row in testset_rows:
            status = row.get("status")
            doc_id = row.get("doc_id")
            question_type = row.get("type")
            by_status[status] = by_status.get(status, 0) + 1
            by_doc[doc_id] = by_doc.get(doc_id, 0) + 1
            by_type[question_type] = by_type.get(question_type, 0) + 1
            status_type[(status, question_type)] = status_type.get((status, question_type), 0) + 1
            status_doc[(status, doc_id)] = status_doc.get((status, doc_id), 0) + 1
        statuses = ordered(by_status, status_order)
        types = ordered(by_type, type_order)
        docs = ordered(by_doc, doc_order)
        accepted_rows = [row for row in testset_rows if row.get("status") == "accepted"]
        empty_span = [row for row in accepted_rows if not str(row.get("gold_span") or "").strip()]
        nonempty_span = [row for row in accepted_rows if str(row.get("gold_span") or "").strip()]
        unanswerable_type = [row for row in accepted_rows if row.get("type") == "unanswerable"]
        anomalies = []
        typed_with_span = [row for row in unanswerable_type if str(row.get("gold_span") or "").strip()]
        if typed_with_span:
            anomalies.append(
                str(len(typed_with_span))
                + " câu accepted có type unanswerable nhưng gold span không rỗng."
            )
        other_empty = [row for row in empty_span if row.get("type") != "unanswerable"]
        if other_empty:
            anomalies.append(
                str(len(other_empty))
                + " câu accepted có gold span rỗng nhưng type không phải unanswerable."
            )
        review_counts = review.get("counts") if isinstance(review, dict) else None
        count_diff = []
        counts_match = None
        if isinstance(review_counts, dict):
            keys = ordered(set(by_status) | set(review_counts), status_order)
            counts_match = True
            for key in keys:
                left = by_status.get(key, 0)
                right = review_counts.get(key, 0)
                if left != right:
                    counts_match = False
                count_diff.append({"status": key, "testset": left, "review_report": right})
        summary_messages = []
        summary_ok = None
        if summary_map:
            scored_values = sorted({summary.get("n_scored") for summary in summary_map.values()})
            unanswerable_values = sorted({summary.get("n_unanswerable") for summary in summary_map.values()})
            question_values = sorted({summary.get("n_questions") for summary in summary_map.values()})
            if len(question_values) == 1 and question_values[0] != len(accepted_rows):
                summary_messages.append(
                    "summary n_questions là "
                    + str(question_values[0])
                    + " còn số dòng accepted trong testset.jsonl là "
                    + str(len(accepted_rows))
                    + "."
                )
            elif len(question_values) > 1:
                summary_messages.append("các summary không thống nhất n_questions: " + str(question_values) + ".")
            if len(scored_values) == 1 and scored_values[0] != len(nonempty_span):
                summary_messages.append(
                    "summary n_scored là "
                    + str(scored_values[0])
                    + " còn số dòng accepted có gold span không rỗng là "
                    + str(len(nonempty_span))
                    + "."
                )
            elif len(scored_values) > 1:
                summary_messages.append("các summary không thống nhất n_scored: " + str(scored_values) + ".")
            if len(unanswerable_values) == 1 and unanswerable_values[0] != len(empty_span):
                summary_messages.append(
                    "summary n_unanswerable là "
                    + str(unanswerable_values[0])
                    + " còn số dòng accepted có gold span rỗng là "
                    + str(len(empty_span))
                    + "."
                )
            elif len(unanswerable_values) > 1:
                summary_messages.append("các summary không thống nhất n_unanswerable: " + str(unanswerable_values) + ".")
            summary_ok = not summary_messages
        type_headers = ["status"] + [str(item) for item in types] + ["tổng"]
        type_rows = []
        for status in statuses:
            values = [status_type.get((status, question_type), 0) for question_type in types]
            type_rows.append([status, *values, sum(values)])
        type_totals = ["tổng"]
        for index, _question_type in enumerate(types):
            type_totals.append(sum(row[index + 1] for row in type_rows))
        type_totals.append(sum(row[-1] for row in type_rows))
        type_rows.append(type_totals)
        doc_headers = ["status"] + [str(item) for item in docs] + ["tổng"]
        doc_rows = []
        for status in statuses:
            values = [status_doc.get((status, doc_id), 0) for doc_id in docs]
            doc_rows.append([status, *values, sum(values)])
        doc_totals = ["tổng"]
        for index, _doc_id in enumerate(docs):
            doc_totals.append(sum(row[index + 1] for row in doc_rows))
        doc_totals.append(sum(row[-1] for row in doc_rows))
        doc_rows.append(doc_totals)
        return {
            "ok": True,
            "n_total": len(testset_rows),
            "statuses": statuses,
            "types": types,
            "docs": docs,
            "by_status": by_status,
            "by_doc": by_doc,
            "by_type": by_type,
            "status_type_headers": type_headers,
            "status_type_rows": type_rows,
            "status_doc_headers": doc_headers,
            "status_doc_rows": doc_rows,
            "accepted": len(accepted_rows),
            "accepted_scored": len(nonempty_span),
            "accepted_empty_span": len(empty_span),
            "accepted_unanswerable_type": len(unanswerable_type),
            "anomalies": anomalies,
            "counts_match": counts_match,
            "count_diff": count_diff,
            "summary_ok": summary_ok,
            "summary_messages": summary_messages,
        }

    def build_review(review, testset_rows):
        if not isinstance(review, dict):
            return {"ok": False}
        overlap = review.get("overlap") or {}
        panel = list(overlap.get("panel") or [])
        votes = overlap.get("votes") or {}
        by_id = {row.get("id"): row for row in (testset_rows or [])}
        reviewer_rows = []
        per_reviewer = review.get("per_reviewer") or {}
        reviewer_order = ordered(per_reviewer, panel)
        for reviewer in reviewer_order:
            bucket = per_reviewer.get(reviewer) or {}
            annotated = bucket.get("annotated") or 0
            accept_votes = bucket.get("accept_votes") or 0
            rate = None if not annotated else accept_votes / annotated
            reviewer_rows.append(
                {
                    "reviewer": reviewer,
                    "tasks": bucket.get("tasks"),
                    "annotated": bucket.get("annotated"),
                    "remaining": bucket.get("remaining"),
                    "annotated_percent": bucket.get("percent"),
                    "accept_votes": accept_votes,
                    "reject_votes": bucket.get("reject_votes"),
                    "accept_rate": rate,
                }
            )
        overlap_status = {}
        for question_id in votes:
            status = (by_id.get(question_id) or {}).get("status", "không có trong testset")
            overlap_status[status] = overlap_status.get(status, 0) + 1
        discussion = []
        for entry in overlap.get("needs_discussion") or []:
            question_id = entry.get("id")
            item = by_id.get(question_id) or {}
            vote_rows = []
            by_reviewer = votes.get(question_id) or {}
            for reviewer in panel:
                ballot = by_reviewer.get(reviewer) if isinstance(by_reviewer, dict) else None
                if not ballot:
                    vote_rows.append(
                        {
                            "reviewer": reviewer,
                            "question_ok": "—",
                            "span_ok": "—",
                            "vote": "—",
                            "note": "—",
                        }
                    )
                else:
                    vote_rows.append(
                        {
                            "reviewer": reviewer,
                            "question_ok": ballot.get("question_ok") or "—",
                            "span_ok": ballot.get("span_ok") or "—",
                            "vote": ballot.get("vote") or "—",
                            "note": ballot.get("note") or "—",
                        }
                    )
            discussion.append(
                {
                    "id": question_id,
                    "question": item.get("question") or "",
                    "status": item.get("status") or "không có trong testset",
                    "type": item.get("type"),
                    "doc_id": item.get("doc_id"),
                    "accept_votes": entry.get("accept_votes"),
                    "reject_votes": entry.get("reject_votes"),
                    "missing": entry.get("missing"),
                    "reason": entry.get("reason"),
                    "votes": vote_rows,
                }
            )
        shares = {}
        for field in ("question_ok", "span_ok", "vote"):
            counts = {}
            total = 0
            for by_reviewer in votes.values():
                if not isinstance(by_reviewer, dict):
                    continue
                for reviewer in panel:
                    ballot = by_reviewer.get(reviewer)
                    if not ballot:
                        continue
                    label = ballot.get(field)
                    if label is None:
                        continue
                    counts[label] = counts.get(label, 0) + 1
                    total += 1
            shares[field] = {"counts": counts, "total": total}
        return {
            "ok": True,
            "panel": panel,
            "threshold": overlap.get("threshold"),
            "overlap_size": overlap.get("size"),
            "n_votes": len(votes),
            "reviewer_rows": reviewer_rows,
            "overlap_status": overlap_status,
            "discussion": discussion,
            "agreement": review.get("agreement") or {},
            "shares": shares,
            "warnings": list(review.get("warnings") or []),
            "votes": votes,
        }

    def _empty_retrieval(message):
        return {
            "ok": False,
            "order": [],
            "rows": [],
            "k_values": [],
            "curve_k": [],
            "k_values_agree": True,
            "mismatches": [message],
            "recompute_ok": False,
            "summary_drift": [],
            "summary_drift_max": None,
            "bad_review": [],
            "n_scored_values": {},
            "n_scored_agree": False,
            "best_mrr": [],
            "best_recall": {},
        }

    def _group_metrics(group_rows, ks):
        return {
            "n": len(group_rows),
            "n_scored": len(scored_rows(group_rows)),
            "mrr": mrr_of(group_rows),
            "recall": {str(k): recall_of(group_rows, k) for k in ks},
        }

    def build_retrieval(summary_map, rows_map, top10_map, curve):
        """Retrieval numbers come from the top-10 JSONL rows.

        Older summary files are only used for review_status and for the
        unscored (unanswerable) question counts. Their recall and MRR are a
        different run and are not copied into the tables.
        """

        chunker_order = ["section", "window", "sentence"]
        summary_map = summary_map or {}
        rows_map = rows_map or {}
        top10_map = top10_map or {}
        order = [name for name in ordered(top10_map, chunker_order) if top10_map.get(name)]
        if not order:
            return _empty_retrieval("Không đọc được file JSONL top-10 nào.")
        curve_ks = list(range(1, 11))
        k_lists = []
        for name in order:
            summary = summary_map.get(name) or {}
            if summary.get("k_values"):
                k_lists.append(list(summary.get("k_values")))
        if k_lists and all(values == k_lists[0] for values in k_lists):
            display_ks = [k for k in k_lists[0] if isinstance(k, int) and not isinstance(k, bool)]
            k_values_agree = True
        elif k_lists:
            display_ks = []
            for values in k_lists:
                for k in values:
                    if k not in display_ks:
                        display_ks.append(k)
            k_values_agree = False
        else:
            display_ks = [1, 3, 5, 10]
            k_values_agree = True
        rows = []
        mismatches = []
        bad_review = []
        curve_map = {}
        if isinstance(curve, dict):
            curve_map = curve.get("chunkers") or {}
        else:
            mismatches.append("recall_curve.json chưa được đọc, nên các metric top-10 chưa được đối chiếu.")
        for name in order:
            top_rows = list(top10_map.get(name) or [])
            summary = summary_map.get(name) or {}
            old_rows = rows_map.get(name)
            unscored = []
            if old_rows:
                for row in old_rows:
                    if not row.get("scored"):
                        item = dict(row)
                        item["scored"] = False
                        unscored.append(item)
            combined = list(top_rows) + unscored
            if old_rows is not None:
                n_unanswerable = len(unscored)
            else:
                n_unanswerable = summary.get("n_unanswerable")
            if n_unanswerable is None:
                n_total = len(top_rows)
            else:
                n_total = len(top_rows) + int(n_unanswerable)
            by_type = {}
            for question_type, group_rows in group_by(combined, "type").items():
                by_type[str(question_type)] = _group_metrics(group_rows, curve_ks)
            by_doc = {}
            for doc_id, group_rows in group_by(combined, "doc_id").items():
                by_doc[str(doc_id)] = _group_metrics(group_rows, curve_ks)
            status = summary.get("review_status")
            if summary and status != "reviewed":
                bad_review.append({"chunker": name, "review_status": status})
            if summary and summary.get("n_scored") != len(top_rows):
                mismatches.append(
                    name
                    + " n_scored: số dòng top-10 "
                    + str(len(top_rows))
                    + ", summary "
                    + str(summary.get("n_scored"))
                    + "."
                )
            if isinstance(curve, dict):
                block = curve_map.get(name)
                if not isinstance(block, dict):
                    mismatches.append(name + ": recall_curve.json không có block của chunker này.")
                else:
                    for k in curve_ks:
                        expected = (block.get("recall") or {}).get(str(k))
                        got = recall_of(top_rows, k)
                        if not same_metric(got, expected):
                            mismatches.append(
                                name
                                + " recall@"
                                + str(k)
                                + ": recall_curve.json "
                                + fmt4(expected)
                                + ", tính lại "
                                + fmt4(got)
                                + "."
                            )
                    if not same_metric(mrr_of(top_rows), block.get("mrr")):
                        mismatches.append(
                            name
                            + " MRR: recall_curve.json "
                            + fmt4(block.get("mrr"))
                            + ", tính lại "
                            + fmt4(mrr_of(top_rows))
                            + "."
                        )
            rows.append(
                {
                    "chunker": name,
                    "run_id": name + "-top10",
                    "review_status": status,
                    "n": n_total,
                    "n_scored": len(top_rows),
                    "n_unanswerable": n_unanswerable,
                    "mrr": mrr_of(top_rows),
                    "recall": {str(k): recall_of(top_rows, k) for k in curve_ks},
                    "by_type": by_type,
                    "by_doc": by_doc,
                }
            )
        drift = []
        max_abs = 0
        compared = False
        for name in order:
            summary = summary_map.get(name) or {}
            old_rows = rows_map.get(name)
            new_rows = list(top10_map.get(name) or [])
            if not old_rows:
                continue
            compared = True
            scored_old = [row for row in old_rows if row.get("scored")]
            for k in summary.get("k_values") or display_ks:
                old_hits = sum(1 for row in scored_old if is_hit(row.get("first_hit_rank"), k))
                new_hits = sum(1 for row in new_rows if is_hit(row.get("first_hit_rank"), k))
                diff = new_hits - old_hits
                max_abs = max(max_abs, abs(diff))
                if diff:
                    drift.append(
                        {
                            "chunker": name,
                            "k": k,
                            "old_hits": old_hits,
                            "new_hits": new_hits,
                            "diff": diff,
                        }
                    )
        n_scored_values = {row["chunker"]: row["n_scored"] for row in rows}
        n_scored_agree = len(set(n_scored_values.values())) == 1

        def best_names(metric_of):
            values = []
            for row in rows:
                value = metric_of(row)
                if value is not None:
                    values.append(value)
            if not values:
                return []
            best = max(values)
            return [
                row["chunker"]
                for row in rows
                if metric_of(row) is not None and same_metric(metric_of(row), best)
            ]

        return {
            "ok": True,
            "order": order,
            "k_values": display_ks,
            "curve_k": curve_ks,
            "k_values_agree": k_values_agree,
            "rows": rows,
            "bad_review": bad_review,
            "n_scored_values": n_scored_values,
            "n_scored_agree": n_scored_agree,
            "mismatches": mismatches,
            "recompute_ok": not mismatches,
            "summary_drift": drift,
            "summary_drift_max": max_abs if compared else None,
            "best_mrr": best_names(lambda row: row["mrr"]),
            "best_recall": {
                str(k): best_names(lambda row, key=str(k): row["recall"].get(key)) for k in display_ks
            },
        }

    def build_errors(summary_map, rows_map, testset_rows, review, top10_map, curve):
        retrieval = build_retrieval(summary_map, rows_map, top10_map, curve)
        if not retrieval.get("ok"):
            return {"ok": False, "retrieval": retrieval}
        order = retrieval["order"]
        indexed = {}
        for name in order:
            indexed[name] = {row.get("id"): row for row in (top10_map.get(name) or [])}
        by_id = {row.get("id"): row for row in (testset_rows or [])}
        overlap = (review or {}).get("overlap") or {} if isinstance(review, dict) else {}
        votes = overlap.get("votes") or {}
        panel = list(overlap.get("panel") or [])
        by_name = {row["chunker"]: row for row in retrieval["rows"]}

        def sort_key(name):
            row = by_name[name]
            recall = (row.get("recall") or {}).get("10")
            mrr_value = row.get("mrr")
            return (
                mrr_value if mrr_value is not None else -1,
                recall if recall is not None else -1,
                -order.index(name),
            )

        best = max(order, key=sort_key)
        common_ids = None
        for name in order:
            scored_ids = {qid for qid, row in indexed[name].items() if row.get("scored")}
            common_ids = scored_ids if common_ids is None else common_ids & scored_ids
        common_ids = common_ids or set()
        id_gaps = []
        for name in order:
            scored_ids = {qid for qid, row in indexed[name].items() if row.get("scored")}
            missing = sorted(scored_ids - common_ids)
            extra = sorted(common_ids - scored_ids)
            if missing or extra:
                id_gaps.append(name + ": các id được chấm khác phần giao.")

        def dissent(question_id):
            record = votes.get(question_id)
            if not isinstance(record, dict):
                return False
            for reviewer in panel:
                ballot = record.get(reviewer)
                if ballot and ballot.get("vote") == "reject":
                    return True
            return False

        def flag_for(question_id):
            flags = []
            if all(not is_hit((indexed[name].get(question_id) or {}).get("first_hit_rank"), 10) for name in order):
                flags.append("mọi chunker đều miss")
            if dissent(question_id):
                flags.append("câu hỏi overlap có reviewer không đồng ý")
            return "; ".join(flags) if flags else "—"

        def vote_rows(question_id):
            record = votes.get(question_id)
            if not isinstance(record, dict):
                return []
            rows = []
            for reviewer in panel:
                ballot = record.get(reviewer)
                if not ballot:
                    rows.append(
                        {"reviewer": reviewer, "question_ok": "—", "span_ok": "—", "vote": "—", "note": "—"}
                    )
                else:
                    rows.append(
                        {
                            "reviewer": reviewer,
                            "question_ok": ballot.get("question_ok") or "—",
                            "span_ok": ballot.get("span_ok") or "—",
                            "vote": ballot.get("vote") or "—",
                            "note": ballot.get("note") or "—",
                        }
                    )
            return rows

        def pack(question_id, primary_rank):
            source = by_id.get(question_id) or {}
            run_row = indexed[best].get(question_id) or {}
            return {
                "id": question_id,
                "question": run_row.get("question") or source.get("question") or "",
                "doc_id": run_row.get("doc_id") or source.get("doc_id"),
                "type": run_row.get("type") or source.get("type"),
                "page": run_row.get("page") if run_row.get("page") is not None else source.get("page"),
                "section": run_row.get("section") or source.get("section") or "",
                "gold_span": run_row.get("gold_span") or source.get("gold_span") or "",
                "reference_answer": source.get("reference_answer") or "",
                "reviewer_note": source.get("reviewer_note") or "",
                "first_hit_rank": rank_text(primary_rank),
                "flag": flag_for(question_id),
                "ranks": {
                    name: rank_text((indexed[name].get(question_id) or {}).get("first_hit_rank")) for name in order
                },
                "votes": vote_rows(question_id),
                "is_overlap": question_id in votes,
            }

        hard = []
        for question_id, row in indexed[best].items():
            if row.get("scored") and not is_hit(row.get("first_hit_rank"), 3):
                hard.append(pack(question_id, row.get("first_hit_rank")))
        hard.sort(key=lambda item: str(item["id"]))

        def all_miss(k):
            found = []
            for question_id in sorted(common_ids, key=str):
                if all(not is_hit((indexed[name].get(question_id) or {}).get("first_hit_rank"), k) for name in order):
                    found.append(pack(question_id, (indexed[best].get(question_id) or {}).get("first_hit_rank")))
            return found

        only_one = []
        for question_id in sorted(common_ids, key=str):
            winners = [
                name
                for name in order
                if is_hit((indexed[name].get(question_id) or {}).get("first_hit_rank"), 10)
            ]
            if len(winners) == 1:
                item = pack(question_id, (indexed[winners[0]].get(question_id) or {}).get("first_hit_rank"))
                item["hit_chunker"] = winners[0]
                only_one.append(item)
        miss_counts = []
        for name in order:
            scored = [row for row in indexed[name].values() if row.get("scored")]
            miss_counts.append(
                {
                    "chunker": name,
                    "n_scored": len(scored),
                    "miss_k3": sum(1 for row in scored if not is_hit(row.get("first_hit_rank"), 3)),
                    "miss_k10": sum(1 for row in scored if not is_hit(row.get("first_hit_rank"), 10)),
                }
            )
        return {
            "ok": True,
            "retrieval": retrieval,
            "best_chunker": best,
            "order": order,
            "common_scored": len(common_ids),
            "id_gaps": id_gaps,
            "hard_misses": hard,
            "all_miss_k3": all_miss(3),
            "all_miss_k10": all_miss(10),
            "only_one": only_one,
            "miss_counts": miss_counts,
        }

    return (
        mo,
        load_notes,
        testset,
        review_report,
        generation_report,
        manifest_text,
        summaries,
        run_rows,
        escape_text,
        fmt4,
        shorten,
        kappa_band,
        md_table,
        md_fill,
        show_table,
        bar_chart,
        build_manifest,
        build_generation,
        build_dataset,
        build_review,
        build_retrieval,
        build_errors,
        top10_rows,
        recall_curve,
    )


@app.cell(hide_code=True)
def _(build_manifest, load_notes, manifest_text, md_fill, mo):
    def _render():
        manifest = build_manifest(manifest_text)
        when = manifest["date_detail"] if manifest["ok"] and manifest["date_detail"] else "không có ngày vì chưa đọc được MANIFEST.md"
        title = md_fill(
            """
            # Báo cáo RAG eval

            Team T024 · doc-rag Retriever · {when}

            Đánh giá Retriever của doc-rag trên test set RAG đã được người review.

            **Điều hướng nhanh**

            - [Tổng quan](#overview) - Mục tiêu, pipeline, định nghĩa metric, và phần được chấm.
            - [Dataset](#dataset) - Số câu hỏi theo status, type và document.
            - [Chất lượng review](#review-quality) - Phiếu của reviewer, agreement trên phần overlap, và các câu chưa chốt.
            - [Metric retrieval](#retrieval-metrics) - recall@k và MRR của từng chunker.
            - [Đường recall@k và các query ví dụ](#recallk-curve-and-example-queries) - recall@k với k = 1..10, và ba ví dụ của chunker section.
            - [Phân rã theo question type và doc](#breakdown-by-question-type-and-doc) - Cùng các metric trên các nhóm nhỏ hơn.
            - [Phân tích lỗi](#error-analysis) - Các miss, chỗ các chunker không khớp nhau, và các dòng cần xem lại.
            - [Kết luận](#conclusions) - Các con số đã tính nói lên điều gì.
            - [Hạn chế và bước tiếp theo](#limitations-and-next-steps) - Cỡ mẫu, kappa, và việc cần làm tiếp.
            """,
            when=when,
        )
        blocks = [title]
        if load_notes:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + note for note in load_notes)),
                    kind="warn",
                    title="Một số file của báo cáo chưa được đọc",
                )
            )
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="overview"></a>

        # Tổng quan
        """
    )
    return


@app.cell(hide_code=True)
def _(
    build_dataset,
    build_generation,
    build_manifest,
    build_retrieval,
    build_review,
    escape_text,
    generation_report,
    manifest_text,
    md_fill,
    mo,
    recall_curve,
    review_report,
    run_rows,
    summaries,
    testset,
    top10_rows,
):
    def _render():
        manifest = build_manifest(manifest_text)
        generation = build_generation(generation_report)
        dataset = build_dataset(testset, review_report, summaries)
        review = build_review(review_report, testset)
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        blocks = []
        if not dataset["ok"] and not retrieval["ok"]:
            blocks.append(mo.md("**Thiếu file.** Các số ở phần tổng quan để trống cho đến khi đọc được `data/testset.jsonl` và `report/results/top10/*-top10.jsonl`."))
            return mo.vstack(blocks)

        n_scored = "—"
        n_unanswerable = "—"
        n_questions = "—"
        if retrieval["ok"] and retrieval["n_scored_agree"]:
            n_scored = next(iter(retrieval["n_scored_values"].values()))
        elif retrieval["ok"]:
            n_scored = ", ".join(str(name) + "=" + str(value) for name, value in retrieval["n_scored_values"].items())
        if retrieval["ok"]:
            unanswerable_values = {row["n_unanswerable"] for row in retrieval["rows"]}
            question_values = {row["n"] for row in retrieval["rows"]}
            if len(unanswerable_values) == 1:
                n_unanswerable = next(iter(unanswerable_values))
            else:
                n_unanswerable = ", ".join(str(value) for value in sorted(unanswerable_values, key=str))
            if len(question_values) == 1:
                n_questions = next(iter(question_values))
        panel = ", ".join(review["panel"]) if review["ok"] else "panel trong review_report.json"
        n_reviewers = len(review["panel"]) if review["ok"] else "—"
        threshold = review["threshold"] if review["ok"] else "—"
        overlap_size = review["overlap_size"] if review["ok"] else "—"
        chunkers = ", ".join(retrieval["order"]) if retrieval["ok"] else "—"
        k_values = ", ".join(str(k) for k in retrieval["k_values"]) if retrieval["ok"] else "—"
        backend = generation["backend"] if generation["ok"] else "—"
        written = generation["written"] if generation["ok"] else "—"
        reason = generation["reason"] if generation["ok"] else ""
        embedding = manifest["embedding"] if manifest["ok"] and manifest["embedding"] else "không ghi trong MANIFEST.md"
        embedding_detail = manifest["embedding_detail"] if manifest["ok"] and manifest["embedding_detail"] else "không ghi trong MANIFEST.md"
        date_detail = manifest["date_detail"] if manifest["ok"] and manifest["date_detail"] else "không ghi trong MANIFEST.md"
        diagram_lines = [
            "candidates.jsonl  (" + str(written) + " câu hỏi, backend " + str(backend) + ")",
            "        |",
            "        v",
            "split_tasks.py  ->  " + str(n_reviewers) + " reviewer (" + str(panel) + ")",
            "        |",
            "        v",
            "Label Studio  (overlap hiện cho mọi reviewer: " + str(overlap_size) + ")",
            "        |",
            "        v",
            "merge_exports.py  ->  testset.jsonl + review_report.json",
            "        |",
            "        v",
            "run_eval.py  chunkers: " + str(chunkers) + "    k = " + str(k_values),
            "        |",
            "        v",
            "báo cáo này",
        ]
        accepted_sentence = ""
        if dataset["ok"]:
            accepted_sentence = (
                "testset.jsonl có "
                + str(dataset["n_total"])
                + " câu hỏi: "
                + str(dataset["accepted"])
                + " accepted, "
                + str(dataset["by_status"].get("rejected", 0))
                + " rejected, "
                + str(dataset["by_status"].get("candidate", 0))
                + " candidate. Số dòng accepted có gold span không rỗng: "
                + str(dataset["accepted_scored"])
                + ". Số dòng accepted có gold span rỗng: "
                + str(dataset["accepted_empty_span"])
                + ". Số dòng accepted có type unanswerable: "
                + str(dataset["accepted_unanswerable_type"])
                + "."
            )
        blocks.append(
            md_fill(
                """
                ## Mục tiêu

                Notebook này báo cáo Retriever của doc-rag trả về chunk chứa gold span đã được người chấp nhận tốt đến mức nào. Notebook không gọi model và không chạy lại retrieval. Số liệu dataset lấy từ test set và review report đã commit. Các metric retrieval được tính lại từ `results/top10/`.

                ## Pipeline

                ```
                {diagram}
                ```

                Câu hỏi không nằm trong overlap đi theo đúng một reviewer. Câu đó chỉ accepted khi Question OK là Accept và Gold span là Yes. Câu hỏi overlap được accepted khi ít nhất {threshold} trong {n_reviewers} reviewer đạt cả hai kiểm tra, bị rejected khi ít nhất {threshold} reviewer trượt một trong hai kiểm tra, còn không thì giữ `candidate` với reviewer note `needs discussion`.

                Các số retrieval bên dưới lấy từ `results/top10/`, một lần chạy lại in-process sau này trên cùng các câu được chấm. Các file `*.summary.json` cũ là một phép đo khác và không được chép vào các bảng này.

                ## Định nghĩa metric

                **recall@k** là tỷ lệ câu được chấm có `first_hit_rank` bằng k hoặc tốt hơn.

                **MRR** là trung bình của `1 / first_hit_rank`. Một miss đóng góp 0.

                **Span containment.** Một chunk được retrieve là hit khi nó chứa gold span sau khi chuẩn hóa khoảng trắng và dấu gạch nối. `first_hit_rank` là rank bắt đầu từ 1 của hit đầu tiên trong top 10. Giá trị là null khi không chunk nào trong số đó chứa span.

                **Fleiss' kappa** là (observed agreement − chance agreement) / (1 − chance agreement). Kappa không xác định khi mọi nhãn đều giống nhau, vì lúc đó chance agreement bằng 1. Cách đọc thông thường (Landis và Koch):

                | kappa | cách đọc |
                | --- | --- |
                | dưới 0 | kém (thấp hơn mức ngẫu nhiên) |
                | 0.00–0.20 | nhẹ |
                | 0.21–0.40 | tạm |
                | 0.41–0.60 | vừa |
                | 0.61–0.80 | đáng kể |
                | 0.81–1.00 | gần như hoàn hảo |

                ## Phần được chấm

                Các file top-10 chứa các câu accepted được chấm. Cộng với các dòng accepted không được chấm, n_questions = {n_questions}, n_scored = {n_scored}, n_unanswerable = {n_unanswerable}.

                {accepted_sentence}

                Câu hỏi có gold span rỗng không được chấm. Trong test set này, những dòng đó là các câu unanswerable. recall@k và MRR không dùng chúng.

                ## Câu hỏi được viết như thế nào

                Backend sinh câu hỏi: `{backend}`. Đó là prompt generator. Các câu hỏi không phải sản phẩm của một lần chạy Ragas hoàn chỉnh.

                Embedding: `{embedding}`.

                Ngày chạy lấy từ MANIFEST.md: {date_detail}.
                """,
                diagram="\n".join(diagram_lines),
                threshold=threshold,
                n_reviewers=n_reviewers,
                n_questions=n_questions,
                n_scored=n_scored,
                n_unanswerable=n_unanswerable,
                accepted_sentence=accepted_sentence,
                backend=backend,
                embedding=embedding,
                date_detail=date_detail,
            )
        )
        if reason:
            blocks.append(mo.md("Lý do ghi trong `ragas_note`:"))
            blocks.append(
                mo.Html(
                    "<pre style='white-space:pre-wrap;font-family:inherit'>"
                    + escape_text(reason)
                    + "</pre>"
                )
            )
        blocks.append(
            md_fill(
                """
                Dòng embedding đầy đủ: {embedding_detail}.

                Các chunker trong snapshot này: {chunkers}. Các giá trị k: {k_values}.
                """,
                embedding_detail=embedding_detail,
                chunkers=chunkers,
                k_values=k_values,
            )
        )
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="dataset"></a>

        # Dataset
        """
    )
    return


@app.cell(hide_code=True)
def _(
    build_dataset,
    build_generation,
    escape_text,
    generation_report,
    md_fill,
    md_table,
    mo,
    review_report,
    summaries,
    testset,
):
    def _render():
        dataset = build_dataset(testset, review_report, summaries)
        if not dataset["ok"]:
            return mo.md("**Thiếu file.** Chưa đọc được `data/testset.jsonl`, nên các bảng dataset để trống.")
        blocks = [
            md_fill(
                """
                `data/testset.jsonl` có **{n_total}** câu hỏi sau review.

                ## Theo status

                {status_table}

                ## Theo document

                {doc_table}

                ## Theo question type

                {type_table}

                ## Status × type

                {status_type}

                ## Status × document

                {status_doc}

                ## Các dòng accepted

                Số câu accepted: **{accepted}**. Trong đó, **{accepted_scored}** có gold span không rỗng (đây là các câu được chấm) và **{accepted_empty}** có gold span rỗng. Số câu accepted có type `unanswerable`: **{accepted_unanswerable}**.
                """,
                n_total=dataset["n_total"],
                status_table=md_table(
                    ["status", "n"],
                    [[status, dataset["by_status"].get(status, 0)] for status in dataset["statuses"]],
                ),
                doc_table=md_table(
                    ["doc_id", "n"],
                    [[doc_id, dataset["by_doc"].get(doc_id, 0)] for doc_id in dataset["docs"]],
                ),
                type_table=md_table(
                    ["type", "n"],
                    [[question_type, dataset["by_type"].get(question_type, 0)] for question_type in dataset["types"]],
                ),
                status_type=md_table(dataset["status_type_headers"], dataset["status_type_rows"]),
                status_doc=md_table(dataset["status_doc_headers"], dataset["status_doc_rows"]),
                accepted=dataset["accepted"],
                accepted_scored=dataset["accepted_scored"],
                accepted_empty=dataset["accepted_empty_span"],
                accepted_unanswerable=dataset["accepted_unanswerable_type"],
            )
        ]
        if dataset["anomalies"]:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + message for message in dataset["anomalies"])),
                    kind="warn",
                    title="Bất thường ở các dòng accepted",
                )
            )
        if dataset["counts_match"] is None:
            blocks.append(mo.md("Không có `counts` trong `review_report.json`, nên bước đối chiếu status được bỏ qua."))
        elif dataset["counts_match"]:
            blocks.append(
                mo.callout(
                    mo.md("Số lượng theo status trong `testset.jsonl` khớp với `counts` trong `review_report.json`."),
                    kind="success",
                )
            )
        else:
            diff_table = md_table(
                ["status", "testset.jsonl", "review_report.json"],
                [[row["status"], row["testset"], row["review_report"]] for row in dataset["count_diff"]],
            )
            blocks.append(
                mo.callout(
                    md_fill(
                        """
                        Số lượng theo status khác nhau giữa `testset.jsonl` và `review_report.json`.

                        {table}
                        """,
                        table=diff_table,
                    ),
                    kind="warn",
                    title="Số lượng không khớp",
                )
            )
        if dataset["summary_ok"] is None:
            blocks.append(mo.md("Không có run summary, nên n_scored chưa được đối chiếu."))
        elif dataset["summary_ok"]:
            blocks.append(
                mo.callout(
                    mo.md(
                        "Summary `n_questions` khớp với số dòng accepted. Summary `n_scored` khớp với số dòng accepted có gold span không rỗng. Summary `n_unanswerable` khớp với số dòng accepted có gold span rỗng."
                    ),
                    kind="success",
                )
            )
        else:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + message for message in dataset["summary_messages"])),
                    kind="warn",
                    title="Số trong summary khác test set",
                )
            )
        generation = build_generation(generation_report)
        if generation["ok"]:
            per_doc = generation["per_doc_written"]
            doc_order = ["nuimages", "mapillary_vistas", "cityscapes"]
            type_order = ["factual", "edge-case", "multi-section", "unanswerable"]
            docs = [doc for doc in doc_order if doc in per_doc] + sorted(
                doc for doc in per_doc if doc not in doc_order
            )
            types = []
            for doc in per_doc.values():
                if isinstance(doc, dict):
                    for question_type in doc:
                        if question_type not in types:
                            types.append(question_type)
            types = [question_type for question_type in type_order if question_type in types] + [
                question_type for question_type in types if question_type not in type_order
            ]
            gen_rows = []
            for doc in docs:
                bucket = per_doc.get(doc) or {}
                values = [bucket.get(question_type, 0) if isinstance(bucket, dict) else "—" for question_type in types]
                gen_rows.append([doc, *values, sum(value for value in values if isinstance(value, int))])
            blocks.append(
                md_fill(
                    """
                    ## Sinh câu hỏi

                    `generation_report.json` ghi backend `{backend}`, written **{written}**, span_check_failed **{failed}**, repaired **{repaired}**.

                    {table}
                    """,
                    backend=generation["backend"],
                    written=generation["written"],
                    failed=generation["span_check_failed"],
                    repaired=generation["repaired"],
                    table=md_table(["doc_id", *types, "tổng"], gen_rows) if docs else "_Không có số theo doc._",
                )
            )
            if generation["written"] != dataset["n_total"]:
                blocks.append(
                    mo.callout(
                        md_fill(
                            "`generation_report` có written = {written} còn `testset.jsonl` có {n_total} dòng.",
                            written=generation["written"],
                            n_total=dataset["n_total"],
                        ),
                        kind="warn",
                    )
                )
            if generation["note"]:
                blocks.append(
                    mo.accordion(
                        {
                            "Toàn bộ ragas_note": mo.Html(
                                "<pre style='white-space:pre-wrap;font-family:inherit'>"
                                + escape_text(generation["note"])
                                + "</pre>"
                            )
                        }
                    )
                )
        else:
            blocks.append(mo.md("Chưa đọc được `data/generation_report.json`."))
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="review-quality"></a>

        # Chất lượng review
        """
    )
    return


@app.cell(hide_code=True)
def _(build_review, escape_text, fmt4, kappa_band, md_fill, md_table, mo, review_report, show_table, testset):
    def _matrix(pairwise, panel):
        lookup = {}
        for key, value in (pairwise or {}).items():
            left, sep, right = str(key).partition("/")
            if not sep:
                continue
            lookup[(left, right)] = value
            lookup[(right, left)] = value
        headers = ["reviewer"] + list(panel)
        rows = []
        for left in panel:
            row = [left]
            for right in panel:
                if left == right:
                    row.append("—")
                else:
                    value = lookup.get((left, right))
                    row.append("—" if value is None else f"{float(value):.1f}")
            rows.append(row)
        return headers, rows

    def _share_phrase(share):
        counts = share["counts"]
        total = share["total"]
        if not total or not counts:
            return "không có vote nào được ghi"
        label, votes = max(counts.items(), key=lambda item: (item[1], str(item[0])))
        percent = 100.0 * votes / total
        listed = ", ".join(
            str(name) + " " + str(count) + " (" + f"{(100.0 * count / total):.1f}%" + ")"
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
        )
        if percent >= 70:
            skew = "phần lớn vote mang cùng một nhãn (" + str(label) + ", " + f"{percent:.1f}%" + " trong " + str(total) + " vote)"
        else:
            skew = "nhãn phổ biến nhất là " + str(label) + " với " + f"{percent:.1f}%" + " trong " + str(total) + " vote"
        return skew + ". Số vote: " + listed

    def _render():
        review = build_review(review_report, testset)
        if not review["ok"]:
            return mo.md("**Thiếu file.** Chưa đọc được `data/review_report.json`, nên phần agreement của reviewer để trống.")
        rate_rows = []
        for row in review["reviewer_rows"]:
            rate = "—" if row["accept_rate"] is None else f"{(100.0 * row['accept_rate']):.1f}%"
            annotated_percent = "—" if row["annotated_percent"] is None else str(row["annotated_percent"])
            rate_rows.append(
                [
                    row["reviewer"],
                    row["tasks"],
                    row["annotated"],
                    row["remaining"],
                    annotated_percent,
                    row["accept_votes"],
                    row["reject_votes"],
                    rate,
                ]
            )
        task_values = {row["tasks"] for row in review["reviewer_rows"]}
        if len(task_values) == 1 and review["overlap_size"] is not None:
            tasks = next(iter(task_values))
            own = None if tasks is None else tasks - review["overlap_size"]
            task_sentence = (
                "Mỗi reviewer có "
                + str(tasks)
                + " task. Overlap size là "
                + str(review["overlap_size"])
                + ", nên "
                + str(own)
                + " task còn lại là riêng của reviewer đó."
            )
        else:
            task_sentence = "Số task nằm trong bảng. Overlap size là " + str(review["overlap_size"]) + "."
        status_order = ["accepted", "rejected", "candidate", "không có trong testset"]
        overlap_keys = [key for key in status_order if key in review["overlap_status"]] + [
            key for key in review["overlap_status"] if key not in status_order
        ]
        blocks = [
            md_fill(
                """
                ## Theo từng reviewer

                Tỷ lệ accept là `accept_votes / annotated`.

                {task_sentence}

                {rate_table}

                ## Overlap

                Khối overlap có size **{overlap_size}** và threshold **{threshold}**. Vote được lưu cho **{n_votes}** câu hỏi. Status của chúng trong `testset.jsonl`:

                {overlap_table}

                Số mục needs_discussion: **{n_discussion}**.
                """,
                task_sentence=task_sentence,
                rate_table=md_table(
                    [
                        "reviewer",
                        "tasks",
                        "annotated",
                        "remaining",
                        "annotated %",
                        "phiếu accept",
                        "phiếu reject",
                        "tỷ lệ accept",
                    ],
                    rate_rows,
                ),
                overlap_size=review["overlap_size"],
                threshold=review["threshold"],
                n_votes=review["n_votes"],
                overlap_table=md_table(
                    ["status", "n"],
                    [[key, review["overlap_status"][key]] for key in overlap_keys],
                ),
                n_discussion=len(review["discussion"]),
            )
        ]
        candidate_n = review["overlap_status"].get("candidate", 0)
        if candidate_n != len(review["discussion"]):
            blocks.append(
                mo.callout(
                    md_fill(
                        "Số dòng overlap có status candidate: {candidate_n}. Số mục needs_discussion: {n_discussion}.",
                        candidate_n=candidate_n,
                        n_discussion=len(review["discussion"]),
                    ),
                    kind="warn",
                    title="Số candidate trong overlap khác needs_discussion",
                )
            )
        agreement_rows = []
        matrices = []
        for check in ("question_ok", "span_ok"):
            block = review["agreement"].get(check) or {}
            kappa = block.get("fleiss_kappa")
            agreement_rows.append(
                [
                    check,
                    "—" if block.get("mean_pairwise_percent") is None else f"{float(block['mean_pairwise_percent']):.1f}",
                    "không xác định" if kappa is None else fmt4(kappa),
                    kappa_band(kappa),
                    block.get("n_overlap"),
                    block.get("n_complete"),
                ]
            )
            headers, matrix_rows = _matrix(block.get("pairwise_percent") or {}, review["panel"])
            matrices.append("### " + check + "\n\n" + md_table(headers, matrix_rows))
        q_block = review["agreement"].get("question_ok") or {}
        s_block = review["agreement"].get("span_ok") or {}
        q_kappa = q_block.get("fleiss_kappa")
        s_kappa = s_block.get("fleiss_kappa")
        blocks.append(
            md_fill(
                """
                ## Pairwise agreement và Fleiss' kappa

                Ô trên đường chéo là cùng một reviewer, nên để trống. Các ô ngoài đường chéo là pairwise percent lấy từ `review_report.json`.

                {matrices}

                {summary}

                Kappa trên `question_ok` là {q_kappa} ({q_band}). Kappa trên `span_ok` là {s_kappa} ({s_band}).

                Với `question_ok`, {q_share}. Với `span_ok`, {s_share}.

                Fleiss' kappa chia (observed agreement − chance agreement) cho (1 − chance agreement). Phân bố nhãn lệch làm chance agreement tăng, nên kappa vẫn thấp dù reviewer thường chọn cùng một nhãn. Phần overlap dùng cho kappa có n_overlap = {q_n} và n_complete = {q_complete} trên `question_ok` (span_ok n_overlap = {s_n}, n_complete = {s_complete}). Với ít item như vậy, ước lượng kappa nhiễu.
                """,
                matrices="\n\n".join(matrices),
                summary=md_table(
                    ["check", "mean pairwise %", "Fleiss' kappa", "cách đọc", "n_overlap", "n_complete"],
                    agreement_rows,
                ),
                q_kappa="không xác định" if q_kappa is None else fmt4(q_kappa),
                q_band=kappa_band(q_kappa),
                s_kappa="không xác định" if s_kappa is None else fmt4(s_kappa),
                s_band=kappa_band(s_kappa),
                q_share=_share_phrase(review["shares"]["question_ok"]),
                s_share=_share_phrase(review["shares"]["span_ok"]),
                q_n=q_block.get("n_overlap"),
                q_complete=q_block.get("n_complete"),
                s_n=s_block.get("n_overlap"),
                s_complete=s_block.get("n_complete"),
            )
        )
        if review["warnings"]:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + escape_text(warning) for warning in review["warnings"])),
                    kind="warn",
                    title="Cảnh báo trong review_report.json",
                )
            )
        else:
            blocks.append(md_fill("Số cảnh báo trong `review_report.json`: {n}.", n=len(review["warnings"])))
        blocks.append(
            md_fill(
                """
                ## Các câu needs_discussion

                {n} câu hỏi overlap nằm trong `needs_discussion`. Dòng có status `candidate` trong testset vẫn chưa được chốt và bị loại khỏi phần chấm.
                """,
                n=len(review["discussion"]),
            )
        )
        if not review["discussion"]:
            blocks.append(mo.md("Danh sách needs_discussion đang trống."))
        else:
            for item in review["discussion"]:
                if item["status"] == "candidate":
                    status_line = "Status trong testset là `candidate`. Câu hỏi này vẫn là candidate và bị loại khỏi phần chấm."
                else:
                    status_line = "Status trong testset là `" + str(item["status"]) + "`."
                blocks.append(md_fill("### `{qid}`\n\n{status_line}", qid=item["id"], status_line=status_line))
                blocks.append(
                    mo.Html(
                        "<p><strong>Câu hỏi</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
                        + escape_text(item["question"])
                        + "</pre>"
                    )
                )
                blocks.append(
                    md_fill(
                        "type `{qtype}`, doc `{doc_id}`, phiếu accept {accept_votes}, phiếu reject {reject_votes}, missing {missing}, reason `{reason}`.",
                        qtype=item["type"],
                        doc_id=item["doc_id"],
                        accept_votes=item["accept_votes"],
                        reject_votes=item["reject_votes"],
                        missing=item["missing"],
                        reason=item["reason"],
                    )
                )
                blocks.append(show_table(item["votes"], label=str(item["id"]) + " — các vote"))
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="retrieval-metrics"></a>

        # Metric retrieval
        """
    )
    return


@app.cell(hide_code=True)
def _(build_retrieval, fmt4, md_fill, md_table, mo, recall_curve, run_rows, summaries, top10_rows):
    def _marked(value, best):
        text = fmt4(value)
        if value is None or best is None:
            return text
        if round(float(value), 4) == round(float(best), 4):
            return "**" + text + "**"
        return text

    def _render():
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md("**Thiếu file.** Không đọc được run nào trong `report/results/top10/*-top10.jsonl`."), None
        ks = retrieval["k_values"]
        headers = ["chunker", "run_id", "review_status", "n", "n_scored", "n_unanswerable"]
        headers += ["recall@" + str(k) for k in ks]
        headers.append("MRR")
        best = {}
        for k in ks:
            values = [row["recall"].get(str(k)) for row in retrieval["rows"] if row["recall"].get(str(k)) is not None]
            best[str(k)] = max(values) if values else None
        mrr_values = [row["mrr"] for row in retrieval["rows"] if row["mrr"] is not None]
        best_mrr = max(mrr_values) if mrr_values else None
        table_rows = []
        for row in retrieval["rows"]:
            table_rows.append(
                [
                    row["chunker"],
                    row["run_id"],
                    row["review_status"],
                    row["n"],
                    row["n_scored"],
                    row["n_unanswerable"],
                    *[_marked(row["recall"].get(str(k)), best[str(k)]) for k in ks],
                    _marked(row["mrr"], best_mrr),
                ]
            )
        best_bits = ["MRR tốt nhất: " + (", ".join("`" + name + "`" for name in retrieval["best_mrr"]) or "—") + " (" + fmt4(best_mrr) + ")."]
        for k in ks:
            names = retrieval["best_recall"].get(str(k)) or []
            best_bits.append(
                "recall@"
                + str(k)
                + " tốt nhất: "
                + (", ".join("`" + name + "`" for name in names) or "—")
                + " ("
                + fmt4(best.get(str(k)))
                + ")."
            )
        blocks = [
            md_fill(
                """
                Các giá trị được tính lại từ `results/top10/<chunker>-top10.jsonl`. Rank là rank theo fused score. Chữ đậm là giá trị tốt nhất trong cột đó. Nếu hòa, mọi chunker hòa đều được in đậm.

                {table}

                {best_lines}

                n_scored theo chunker: {scored}.
                """,
                table=md_table(headers, table_rows),
                best_lines=" ".join(best_bits),
                scored=", ".join("`" + name + "` " + str(value) for name, value in retrieval["n_scored_values"].items()),
            )
        ]
        if not retrieval["k_values_agree"]:
            blocks.append(
                mo.callout(
                    mo.md("Các file summary không liệt kê cùng `k_values`. Bảng dùng hợp của chúng, theo thứ tự gặp lần đầu."),
                    kind="warn",
                )
            )
        if retrieval["bad_review"] or not retrieval["n_scored_agree"]:
            lines = []
            for item in retrieval["bad_review"]:
                lines.append(
                    "`" + str(item["chunker"]) + "` có review_status `" + str(item["review_status"]) + "`."
                )
            if not retrieval["n_scored_agree"]:
                lines.append(
                    "n_scored không thống nhất: "
                    + ", ".join(str(name) + "=" + str(value) for name, value in retrieval["n_scored_values"].items())
                    + "."
                )
            blocks.append(mo.callout(mo.md("\n".join("- " + line for line in lines)), kind="warn", title="Kiểm tra run"))
        else:
            scored = next(iter(retrieval["n_scored_values"].values()))
            blocks.append(
                mo.callout(
                    md_fill(
                        "Cả {n_runs} chunker đều thống nhất n_scored = {scored}. review_status trong summary đã lưu là `reviewed`.",
                        n_runs=len(retrieval["rows"]),
                        scored=scored,
                    ),
                    kind="success",
                    title="Kiểm tra run",
                )
            )
        if retrieval["recompute_ok"]:
            blocks.append(
                mo.callout(
                    mo.md(
                        "recall@k với k = 1..10 và MRR tính lại từ từng JSONL top-10 khớp `results/top10/recall_curve.json` ở 4 chữ số thập phân."
                    ),
                    kind="success",
                    title="Tính lại",
                )
            )
        else:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + item for item in retrieval["mismatches"])),
                    kind="warn",
                    title="Tính lại không khớp",
                )
            )
        options = [str(k) for k in ks] or ["1"]
        default = "5" if "5" in options else options[-1]
        picker = mo.ui.dropdown(options=options, value=default, label="k")
        blocks.append(md_fill("Xem recall theo k (bảng phía trên đã liệt kê mọi k). Mặc định k = {default}.", default=default))
        blocks.append(picker)
        return mo.vstack(blocks), picker

    _retrieval_view, k_picker = _render()
    _retrieval_view
    return (k_picker,)


@app.cell(hide_code=True)
def _(build_retrieval, fmt4, k_picker, md_fill, mo, recall_curve, run_rows, summaries, top10_rows):
    def _render():
        if k_picker is None or k_picker.value is None:
            return mo.md("")
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md("")
        k = str(k_picker.value)
        bits = []
        for row in retrieval["rows"]:
            bits.append(
                "`"
                + str(row["chunker"])
                + "` "
                + fmt4(row["recall"].get(k))
                + " (n_scored="
                + str(row["n_scored"])
                + ")"
            )
        return md_fill(
            "Tại k = {k}, recall@k là {bits}.",
            k=k,
            bits="; ".join(bits),
        )

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="recallk-curve-and-example-queries"></a>

        # Đường recall@k và các query ví dụ
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        Đường này là recall@k trên mọi câu được chấm, k từ 1 đến 10. Ba ví dụ là các câu của chunker section, được chọn trong code từ `section-top10.jsonl` (không cố định id): id đầu tiên có hit ở rank 1, hit thấp nhất có rank nằm trong 3..7 (hòa thì lấy id nhỏ hơn), và id đầu tiên không có hit trong top 10.
        """
    )
    return


@app.cell(hide_code=True)
def _(escape_text, md_table, mo, shorten):
    try:
        import matplotlib.pyplot as plt

        plt.rcParams["font.family"] = "DejaVu Sans"
    except ImportError:
        plt = None

    def plot_recall_curve(retrieval):
        if plt is None:
            return mo.md("**Chưa cài matplotlib**, nên không vẽ được đường recall.")
        rows = retrieval.get("rows") or []
        if not rows:
            return mo.md("**Không có chunker để vẽ.**")
        colors = {"section": "#2196F3", "window": "#FF9800", "sentence": "#9C27B0"}
        dashes = {
            "section": (0, (5, 3)),
            "window": (0, (3, 1.5, 1, 1.5)),
            "sentence": (0, (1, 1.4)),
        }
        fallback = ["#2196F3", "#FF9800", "#9C27B0"]
        curve_k = list(retrieval.get("curve_k") or range(1, 11))
        plt.close("all")
        fig, ax = plt.subplots(figsize=(11.2, 6.4))
        series = []
        for index, row in enumerate(rows):
            name = str(row["chunker"])
            color = colors.get(name, fallback[index % len(fallback)])
            ys = []
            for k in curve_k:
                value = (row.get("recall") or {}).get(str(k))
                ys.append(None if value is None else float(value) * 100.0)
            mrr_value = row.get("mrr")
            mrr_pct = None if mrr_value is None else float(mrr_value) * 100.0
            series.append((name, color, ys, mrr_pct))
            plot_ys = [0.0 if value is None else value for value in ys]
            ax.plot(
                curve_k,
                plot_ys,
                color=color,
                marker="o",
                linewidth=2.1,
                markersize=7,
                label=name,
                zorder=3,
            )
            if mrr_pct is not None:
                ax.axhline(
                    mrr_pct,
                    color=color,
                    linestyle=dashes.get(name, "--"),
                    linewidth=1.15,
                    alpha=0.85,
                    label=name + " MRR",
                    zorder=1,
                )
        # Labels sit in the empty band under the curves so the twelve callouts do not cover each other.
        finite = [value for _name, _color, ys, _mrr in series for value in ys if value is not None]
        floor = min(finite) if finite else 0.0
        slots = [40, 27, 14]
        if floor >= max(slots) + 12:
            x_for = {}
            usable = [k for k in (1, 3, 5, 10) if k in curve_k]
            for k in usable:
                if k >= 9:
                    x_for[k] = k - 1.3
                elif k <= 1:
                    x_for[k] = k + 0.55
                else:
                    x_for[k] = k + 0.7
            for k in usable:
                group = []
                for name, _color, ys, _mrr in series:
                    value = ys[curve_k.index(k)]
                    if value is not None:
                        group.append((name, value))
                group.sort(key=lambda item: -item[1])
                for (name, value), slot in zip(group, slots):
                    ax.annotate(
                        name + " " + f"{value:.1f}%",
                        xy=(k, value),
                        xytext=(x_for[k], slot),
                        ha="center",
                        va="center",
                        fontsize=8,
                        color="#b71c1c",
                        arrowprops=dict(arrowstyle="->", color="#e53935", lw=1.0),
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#ef9a9a", lw=0.6, alpha=0.95),
                        annotation_clip=False,
                        zorder=5,
                    )
        ax.set_xlim(0.35, max(curve_k) + 0.65)
        ax.set_ylim(0, 105)
        ax.set_xticks(curve_k)
        ax.set_xlabel("k")
        ax.set_ylabel("recall@k (%)")
        ax.set_title("Recall@k")
        ax.grid(True, alpha=0.3)
        ax.legend(
            loc="center left",
            bbox_to_anchor=(1.01, 0.58),
            fontsize=8,
            framealpha=0.95,
            borderaxespad=0.2,
        )
        fig.tight_layout(rect=(0, 0, 0.84, 1))
        return plt.gca()

    def plot_top_k_scores(chunks):
        if plt is None:
            return mo.md("**Chưa cài matplotlib**, nên không vẽ được biểu đồ cột.")
        plt.close("all")
        fig, ax = plt.subplots(figsize=(10, 4))
        chunks = list(chunks or [])
        ax.set_title("Cosine similarity top-10 (xanh lá = chunk chứa gold span, đỏ = không)")
        ax.set_ylabel("Cosine similarity (Qwen3-Embedding-0.6B)")
        ax.grid(axis="y", alpha=0.3)
        if not chunks:
            ax.set_ylim(0, 1)
            fig.tight_layout()
            return plt.gca()
        ranks = [chunk.get("rank") for chunk in chunks]
        cosines = [float(chunk.get("cosine") or 0.0) for chunk in chunks]
        colors = ["#4CAF50" if chunk.get("hit") else "#F44336" for chunk in chunks]
        ax.bar(ranks, cosines, color=colors, edgecolor="white", linewidth=1.5, width=0.6)
        for rank, cosine in zip(ranks, cosines):
            ax.text(rank, cosine, f"{cosine:.4f}", ha="center", va="bottom", fontsize=8)
        labels = []
        for chunk in chunks:
            page = chunk.get("page_start")
            page_label = "—" if page is None else str(page)
            labels.append("Rank " + str(chunk.get("rank")) + "\np." + page_label)
        ax.set_xticks(ranks)
        ax.set_xticklabels(labels)
        ymax = max(cosines) if cosines else 1.0
        if ymax <= 0:
            ymax = 1.0
        ax.set_ylim(0, ymax * 1.12)
        fig.tight_layout()
        return plt.gca()

    def show_top_k_details(chunks):
        headers = ["Rank", "Fused Score", "Cosine", "Section", "Page", "Khớp", "Snippet"]
        table_rows = []
        for chunk in chunks or []:
            start = chunk.get("page_start")
            end = chunk.get("page_end")
            if start is None:
                page = "—"
            elif end is None or end == start:
                page = str(start)
            else:
                page = str(start) + "–" + str(end)
            fused = chunk.get("fused_score")
            cosine = chunk.get("cosine")
            table_rows.append(
                [
                    chunk.get("rank"),
                    "—" if fused is None else f"{float(fused):.6f}",
                    "—" if cosine is None else f"{float(cosine):.6f}",
                    chunk.get("section_path") or "—",
                    page,
                    "✅" if chunk.get("hit") else "❌",
                    shorten(chunk.get("text_snippet"), 200),
                ]
            )
        blocks = [mo.md("**📊 Chi tiết retrieval top-10**")]
        if table_rows:
            blocks.append(mo.md(md_table(headers, table_rows)))
        else:
            blocks.append(mo.md("_Không có chunk được retrieve._"))
        if chunks is not None and len(chunks) < 10:
            blocks.append(mo.md("Query này trả về " + str(len(chunks)) + " chunk trong file top-10."))
        return mo.vstack(blocks)

    def choose_section_examples(rows):
        if not rows:
            return None
        ordered_rows = sorted(rows, key=lambda row: str(row.get("id")))

        def _rank(row):
            rank = row.get("first_hit_rank")
            if isinstance(rank, bool) or not isinstance(rank, int):
                return None
            return rank

        rank1 = next((row for row in ordered_rows if _rank(row) == 1), None)
        misses = [row for row in ordered_rows if row.get("first_hit_rank") is None]
        miss = misses[0] if misses else None
        band = [row for row in ordered_rows if _rank(row) is not None and 3 <= _rank(row) <= 7]
        mid = None
        if band:
            lowest = max(_rank(row) for row in band)
            mid = next(row for row in band if _rank(row) == lowest)
        else:
            ge3 = [row for row in ordered_rows if _rank(row) is not None and _rank(row) >= 3]
            if ge3:
                mid = min(ge3, key=lambda row: (abs(_rank(row) - 5), str(row.get("id"))))
        if rank1 is None or mid is None or miss is None:
            return None
        return {"rank1": rank1, "mid": mid, "miss": miss}

    def example_header(row, label):
        chunks = row.get("top10") or []
        top = chunks[0] if chunks else None
        mark = "✅ Đúng" if top and top.get("hit") else "❌ Sai"
        rank = row.get("first_hit_rank")
        rank_label = "null" if rank is None else str(rank)
        body = (
            "<p><strong>Câu hỏi.</strong> "
            + escape_text(row.get("question"))
            + "</p><p><strong>Gold span.</strong> "
            + escape_text(shorten(row.get("gold_span"), 280))
            + "</p><p>id <code>"
            + escape_text(row.get("id"))
            + "</code>, doc <code>"
            + escape_text(row.get("doc_id"))
            + "</code>, type <code>"
            + escape_text(row.get("type"))
            + "</code>, first_hit_rank <code>"
            + escape_text(rank_label)
            + "</code>. Khớp ở top-1: "
            + mark
            + ".</p>"
        )
        return mo.vstack([mo.md("### " + label), mo.Html(body)])

    return (
        plot_recall_curve,
        plot_top_k_scores,
        show_top_k_details,
        choose_section_examples,
        example_header,
    )


@app.cell(hide_code=True)
def _(build_retrieval, mo, plot_recall_curve, recall_curve, run_rows, summaries, top10_rows):
    def _render():
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md(
                "**Thiếu file.** Đường recall@k cần `report/results/top10/<chunker>-top10.jsonl`."
            )
        return plot_recall_curve(retrieval)

    _render()
    return


@app.cell(hide_code=True)
def _(build_retrieval, fmt4, md_table, mo, recall_curve, run_rows, summaries, top10_rows):
    def _render():
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md("")
        headers = ["Chunker", "R@1", "R@3", "R@5", "R@10", "MRR"]
        table_rows = []
        for row in retrieval["rows"]:
            recall = row.get("recall") or {}
            table_rows.append(
                [
                    row["chunker"],
                    fmt4(recall.get("1")),
                    fmt4(recall.get("3")),
                    fmt4(recall.get("5")),
                    fmt4(recall.get("10")),
                    fmt4(row.get("mrr")),
                ]
            )
        table = md_table(headers, table_rows)
        return mo.md(
            table
            + r"""

## Cách đọc đường này

Trục ngang là \(k\), số chunk được retrieve cho phép. Trục chạy từ 1 đến 10. Trục dọc là recall@k tính theo phần trăm số câu được chấm. Một điểm tại \(k = 3\) là phần trăm câu được chấm có gold span xuất hiện trong top 3 chunk.

Mỗi đường liền là một chunker: section `#2196F3`, window `#FF9800`, sentence `#9C27B0`. Mũi tên đỏ đánh dấu recall tại \(k = 1, 3, 5, 10\). Nhãn là recall đó theo phần trăm. Đường ngang đứt nét cùng màu là MRR của chunker đó nhân 100, để nằm trên cùng một trục. MRR của window và sentence gần nhau, nên hai đường đứt đó gần như chồng lên nhau. MRR bản thân không phải một giá trị recall.

$$
\mathrm{recall@}k = \frac{|\{q \in Q : \mathrm{rank}(q) \leq k\}|}{|Q|}
$$

\(Q\) là tập các câu được chấm. \(\mathrm{rank}(q)\) là `first_hit_rank`. Một câu được tính vào recall@k chỉ khi rank đó là số nguyên từ 1 đến \(k\).

$$
\mathrm{MRR} = \frac{1}{|Q|} \sum_{q \in Q} rr(q)
$$

\(rr(q) = 1/\mathrm{rank}(q)\) khi gold span nằm trong top 10, và \(rr(q) = 0\) khi `first_hit_rank` là null.

Bảng là cùng recall và MRR ở dạng phân số, làm tròn 4 chữ số thập phân. Đồ thị nhân các phân số đó với 100. Các nhãn đỏ được đặt so le bên dưới đường để mười hai chú thích không đè lên nhau.
"""
        )

    _render()
    return


@app.cell(hide_code=True)
def _(choose_section_examples, top10_rows):
    section_rows = top10_rows.get("section") if isinstance(top10_rows, dict) else None
    section_examples = choose_section_examples(section_rows) if section_rows else None
    return (section_examples,)


@app.cell(hide_code=True)
def _(mo, section_examples):
    def _render():
        if not section_examples:
            return mo.md(
                "**Thiếu file.** Các query ví dụ cần `report/results/top10/section-top10.jsonl`, gồm một hit ở rank 1, một hit ở rank 3..7, và một miss."
            )
        return mo.md(
            r"""
            ## Query ví dụ (chunker section)

            Mỗi ví dụ là một câu được chấm. Bảng chi tiết cho thấy fused score đã quyết định rank, và cosine của Qwen3-Embedding-0.6B, thứ không quyết định rank. Biểu đồ cột dùng cosine làm chiều cao cột.
            """
        )

    _render()
    return


@app.cell(hide_code=True)
def _(example_header, section_examples):
    def _render():
        if not section_examples:
            return None
        return example_header(section_examples["rank1"], "Ví dụ A — hit ở rank 1")

    _render()
    return


@app.cell(hide_code=True)
def _(section_examples, show_top_k_details):
    def _render():
        if not section_examples:
            return None
        return show_top_k_details(section_examples["rank1"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(plot_top_k_scores, section_examples):
    def _render():
        if not section_examples:
            return None
        return plot_top_k_scores(section_examples["rank1"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(mo, section_examples):
    def _render():
        if not section_examples:
            return mo.md("")
        return mo.md(
            "Chiều cao cột là cosine similarity. Retriever xếp hạng theo fused score (hybrid reciprocal rank fusion), nên các cột này không nhất thiết giảm dần."
        )

    _render()
    return


@app.cell(hide_code=True)
def _(example_header, section_examples):
    def _render():
        if not section_examples:
            return None
        return example_header(section_examples["mid"], "Ví dụ B — hit đầu tiên ở rank 3 trở đi")

    _render()
    return


@app.cell(hide_code=True)
def _(section_examples, show_top_k_details):
    def _render():
        if not section_examples:
            return None
        return show_top_k_details(section_examples["mid"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(plot_top_k_scores, section_examples):
    def _render():
        if not section_examples:
            return None
        return plot_top_k_scores(section_examples["mid"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(mo, section_examples):
    def _render():
        if not section_examples:
            return mo.md("")
        return mo.md(
            "Chiều cao cột là cosine similarity. Retriever xếp hạng theo fused score (hybrid reciprocal rank fusion), nên các cột này không nhất thiết giảm dần."
        )

    _render()
    return


@app.cell(hide_code=True)
def _(example_header, fmt4, mo, section_examples):
    def _hit(rank, k):
        return isinstance(rank, int) and not isinstance(rank, bool) and 1 <= rank <= k

    def _render():
        if not section_examples:
            return mo.md("")
        row = section_examples["mid"]
        rank = row.get("first_hit_rank")
        if rank is None:
            rr_phrase = "`first_hit_rank` là null, nên reciprocal rank bằng 0"
            rr = "0"
        else:
            rr = fmt4(1.0 / rank)
            rr_phrase = "1/" + str(rank) + " = " + rr
        bits = []
        for k in (1, 3, 5, 10):
            bits.append("recall@" + str(k) + " = " + ("1" if _hit(rank, k) else "0"))
        return mo.md(
            "### Cách đọc ví dụ\n\n"
            "Phần này đi theo ví dụ B, `"
            + str(row.get("id"))
            + "`, câu của chunker section có chunk đúng đầu tiên là hit thấp nhất trong khoảng rank 3..7.\n\n"
            "Chunk đầu tiên chứa gold span nằm ở rank "
            + str(rank)
            + ". Top-1 "
            + ("đúng" if _hit(rank, 1) else "sai")
            + ". Với riêng câu này, recall@k bằng 1 khi rank đó bằng k hoặc tốt hơn, và bằng 0 nếu không: "
            + ", ".join(bits)
            + ".\n\n"
            "Reciprocal rank của câu này là "
            + rr_phrase
            + ". MRR lấy trung bình giá trị đó trên mọi câu được chấm, nên câu này đóng góp "
            + rr
            + ".\n\n"
            "Trên biểu đồ cột, xanh lá là chunk chứa gold span và đỏ là chunk không chứa. "
            "Chiều cao cột là cosine similarity từ Qwen3-Embedding-0.6B. "
            "Thứ tự từ trái sang phải là rank theo fused score, nên một cột xanh có thể cao hơn hoặc thấp hơn các cột đỏ bên cạnh."
        )

    _render()
    return


@app.cell(hide_code=True)
def _(example_header, section_examples):
    def _render():
        if not section_examples:
            return None
        return example_header(section_examples["miss"], "Ví dụ C — miss trong top 10")

    _render()
    return


@app.cell(hide_code=True)
def _(section_examples, show_top_k_details):
    def _render():
        if not section_examples:
            return None
        return show_top_k_details(section_examples["miss"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(plot_top_k_scores, section_examples):
    def _render():
        if not section_examples:
            return None
        return plot_top_k_scores(section_examples["miss"].get("top10") or [])

    _render()
    return


@app.cell(hide_code=True)
def _(mo, section_examples):
    def _render():
        if not section_examples:
            return mo.md("")
        return mo.md(
            "Chiều cao cột là cosine similarity. Retriever xếp hạng theo fused score (hybrid reciprocal rank fusion), nên các cột này không nhất thiết giảm dần. Không chunk nào trong mười chunk này chứa gold span, nên mọi cột đều đỏ và recall@10 của câu này là 0."
        )

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="breakdown-by-question-type-and-doc"></a>

        # Phân rã theo question type và doc
        """
    )
    return


@app.cell(hide_code=True)
def _(bar_chart, build_retrieval, fmt4, md_fill, md_table, mo, recall_curve, run_rows, summaries, top10_rows):
    def _metric_cell(block, key, best):
        if not block or not block.get("n_scored"):
            n_scored = 0 if not block else block.get("n_scored")
            return "— (n=" + str(n_scored) + ")"
        if key == "mrr":
            value = block.get("mrr")
        else:
            value = (block.get("recall") or {}).get(key)
        text = fmt4(value) + " (n=" + str(block.get("n_scored")) + ")"
        if value is not None and best is not None and round(float(value), 4) == round(float(best), 4):
            return "**" + text + "**"
        return text

    def _render():
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md("**Thiếu file.** Các bảng phân rã cần `report/results/top10/*-top10.jsonl`.")
        type_order = ["factual", "edge-case", "multi-section", "unanswerable"]
        doc_order = ["nuimages", "mapillary_vistas", "cityscapes"]
        type_names = []
        doc_names = []
        for row in retrieval["rows"]:
            for name in row["by_type"]:
                if name not in type_names:
                    type_names.append(name)
            for name in row["by_doc"]:
                if name not in doc_names:
                    doc_names.append(name)
        type_names = [name for name in type_order if name in type_names] + [
            name for name in type_names if name not in type_order
        ]
        doc_names = [name for name in doc_order if name in doc_names] + [
            name for name in doc_names if name not in doc_order
        ]
        ks = retrieval["k_values"]
        blocks = [
            md_fill(
                """
                Mỗi số được tính lại từ các dòng top-10 của chunker đó. `n_scored` là mẫu số và được in cạnh các metric. Các nhóm unanswerable có `n_scored` bằng 0, nên recall và MRR là null.
                """
            )
        ]
        headers = ["nhóm", "n", "n_scored"] + ["recall@" + str(k) for k in ks] + ["MRR"]
        for row in retrieval["rows"]:
            type_rows = []
            for name in type_names:
                block = row["by_type"].get(name) or {}
                type_rows.append(
                    [
                        name,
                        block.get("n", 0),
                        block.get("n_scored", 0),
                        *[fmt4((block.get("recall") or {}).get(str(k))) for k in ks],
                        fmt4(block.get("mrr")),
                    ]
                )
            doc_rows = []
            for name in doc_names:
                block = row["by_doc"].get(name) or {}
                doc_rows.append(
                    [
                        name,
                        block.get("n", 0),
                        block.get("n_scored", 0),
                        *[fmt4((block.get("recall") or {}).get(str(k))) for k in ks],
                        fmt4(block.get("mrr")),
                    ]
                )
            blocks.append(
                md_fill(
                    """
                    ## {chunker}

                    Lần chạy `{run_id}`. n_scored tổng thể = {n_scored}.

                    ### Theo question type

                    {type_table}

                    ### Theo document

                    {doc_table}
                    """,
                    chunker=row["chunker"],
                    run_id=row["run_id"],
                    n_scored=row["n_scored"],
                    type_table=md_table(headers, type_rows),
                    doc_table=md_table(headers, doc_rows),
                )
            )
        focus_k = "5" if "5" in [str(k) for k in ks] else str(ks[-1] if ks else "")
        side_headers = ["nhóm", "loại", "n_scored"]
        for row in retrieval["rows"]:
            side_headers.append(str(row["chunker"]) + " recall@" + focus_k)
        for row in retrieval["rows"]:
            side_headers.append(str(row["chunker"]) + " MRR")
        side_rows = []
        for kind, names in (("type", type_names), ("doc", doc_names)):
            for name in names:
                blocks_for_group = []
                for row in retrieval["rows"]:
                    source = row["by_type"] if kind == "type" else row["by_doc"]
                    blocks_for_group.append(source.get(name) or {})
                recall_values = []
                mrr_values = []
                for block in blocks_for_group:
                    if block.get("n_scored"):
                        recall_values.append((block.get("recall") or {}).get(focus_k))
                        mrr_values.append(block.get("mrr"))
                recall_values = [value for value in recall_values if value is not None]
                mrr_values = [value for value in mrr_values if value is not None]
                best_recall = max(recall_values) if recall_values else None
                best_mrr = max(mrr_values) if mrr_values else None
                n_values = [block.get("n_scored", 0) for block in blocks_for_group]
                n_label = str(n_values[0]) if n_values and all(value == n_values[0] for value in n_values) else ", ".join(str(value) for value in n_values)
                side_rows.append(
                    [
                        name,
                        kind,
                        n_label,
                        *[_metric_cell(block, focus_k, best_recall) for block in blocks_for_group],
                        *[_metric_cell(block, "mrr", best_mrr) for block in blocks_for_group],
                    ]
                )
        blocks.append(
            md_fill(
                """
                ## Đặt cạnh nhau

                recall@{focus_k} và MRR giữa các chunker. Chữ đậm là giá trị tốt nhất trên dòng đó, trong các nhóm được chấm. `n_scored` nằm trong ô metric.

                {table}
                """,
                focus_k=focus_k,
                table=md_table(side_headers, side_rows),
            )
        )
        palette = {"section": "#2563eb", "window": "#059669", "sentence": "#d97706"}
        fallback = ["#2563eb", "#059669", "#d97706", "#7c3aed"]
        mrr_items = []
        recall_items = []
        recall10_key = "10" if "10" in [str(k) for k in ks] else (str(ks[-1]) if ks else None)
        for index, row in enumerate(retrieval["rows"]):
            color = palette.get(row["chunker"], fallback[index % len(fallback)])
            label = str(row["chunker"]) + " (n=" + str(row["n_scored"]) + ")"
            mrr_items.append((label, row["mrr"], color))
            if recall10_key is not None:
                recall_items.append((label, row["recall"].get(recall10_key), color))
        blocks.append(md_fill("## Thanh tổng thể\n\nĐộ dài thanh là metric. Nhãn mang n_scored."))
        blocks.append(bar_chart(mrr_items, "MRR"))
        if recall10_key is not None:
            blocks.append(bar_chart(recall_items, "recall@" + recall10_key))
        small = []
        for row in retrieval["rows"]:
            for kind, source in (("type", row["by_type"]), ("doc", row["by_doc"])):
                for name, block in source.items():
                    n_scored = block.get("n_scored") or 0
                    if n_scored:
                        small.append((n_scored, row["chunker"], kind, name))
        if small:
            minimum = min(item[0] for item in small)
            names = [
                "`" + chunker + "` " + kind + " `" + str(name) + "`"
                for n_scored, chunker, kind, name in small
                if n_scored == minimum
            ]
            blocks.append(
                md_fill(
                    "Nhóm được chấm nhỏ nhất: n_scored = {minimum} ({names}).",
                    minimum=minimum,
                    names="; ".join(names),
                )
            )
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="error-analysis"></a>

        # Phân tích lỗi
        """
    )
    return


@app.cell(hide_code=True)
def _(
    build_errors,
    escape_text,
    md_fill,
    md_table,
    mo,
    recall_curve,
    review_report,
    run_rows,
    shorten,
    show_table,
    summaries,
    testset,
    top10_rows,
):
    def _table_row(item, extra=None):
        row = {
            "id": item["id"],
            "question": item["question"],
            "doc_id": item["doc_id"],
            "type": item["type"],
            "page": "—" if item["page"] is None else str(item["page"]),
            "section": item["section"] or "—",
            "gold_span": shorten(item["gold_span"], 200),
            "first_hit_rank": item["first_hit_rank"],
            "reference_answer": shorten(item["reference_answer"], 200),
            "reviewer_note": shorten(item["reviewer_note"], 200),
            "flag": item["flag"],
        }
        if extra:
            row.update(extra)
        return row

    def _detail(item, order):
        chunks = [
            "<p><strong>Câu hỏi</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
            + escape_text(item["question"])
            + "</pre>",
            "<p><strong>Gold span</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
            + escape_text(item["gold_span"])
            + "</pre>",
            "<p><strong>Reference answer</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
            + escape_text(item["reference_answer"] or "(trống)")
            + "</pre>",
            "<p><strong>Ghi chú của reviewer</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
            + escape_text(item["reviewer_note"] or "(trống)")
            + "</pre>",
        ]
        rank_line = ", ".join(str(name) + "=" + str(item["ranks"][name]) for name in order)
        chunks.append("<p><strong>first_hit_rank</strong></p><p>" + escape_text(rank_line) + "</p>")
        chunks.append("<p><strong>Flag</strong></p><p>" + escape_text(item["flag"]) + "</p>")
        if item["is_overlap"]:
            vote_lines = []
            for ballot in item["votes"]:
                vote_lines.append(
                    str(ballot["reviewer"])
                    + ": question_ok="
                    + str(ballot["question_ok"])
                    + ", span_ok="
                    + str(ballot["span_ok"])
                    + ", vote="
                    + str(ballot["vote"])
                    + ", note="
                    + str(ballot["note"])
                )
            chunks.append(
                "<p><strong>Vote trên overlap</strong></p><pre style='white-space:pre-wrap;font-family:inherit'>"
                + escape_text("\n".join(vote_lines))
                + "</pre>"
            )
        else:
            chunks.append("<p>Không phải câu hỏi overlap.</p>")
        return mo.Html("".join(chunks))

    def _render():
        errors = build_errors(summaries, run_rows, testset, review_report, top10_rows, recall_curve)
        if not errors["ok"]:
            return mo.md("**Thiếu file.** Phân tích lỗi cần `report/results/top10/*-top10.jsonl`.")
        order = errors["order"]
        blocks = [
            md_fill(
                """
                Chunker tốt nhất theo MRR là `{best}`. Hòa thì xét recall@10 cao hơn, rồi đến thứ tự hiển thị ({order}).

                Miss tại k nghĩa là `first_hit_rank` là null hoặc lớn hơn k. Cột flag chỉ để đánh dấu cần xem tay. Nó không có nghĩa là nhãn sai.

                - `mọi chunker đều miss`: mọi chunker có `first_hit_rank` null hoặc lớn hơn 10.
                - `câu hỏi overlap có reviewer không đồng ý`: id nằm trong `overlap.votes` và ít nhất một reviewer có `vote` = `reject`.

                Số id được chấm chung giữa các chunker: **{common}**.
                """,
                best=errors["best_chunker"],
                order=", ".join(order),
                common=errors["common_scored"],
            )
        ]
        if errors["id_gaps"]:
            blocks.append(
                mo.callout(
                    mo.md("\n".join("- " + gap for gap in errors["id_gaps"])),
                    kind="warn",
                    title="Các id được chấm khác nhau giữa các run",
                )
            )
        blocks.append(
            md_fill(
                """
                ## Số miss

                {table}
                """,
                table=md_table(
                    ["chunker", "n_scored", "miss tại k=3", "miss tại k=10"],
                    [
                        [row["chunker"], row["n_scored"], row["miss_k3"], row["miss_k10"]]
                        for row in errors["miss_counts"]
                    ],
                ),
            )
        )
        blocks.append(
            md_fill(
                """
                ## {best}: các câu được chấm có first_hit_rank null hoặc lớn hơn 3

                {n} câu. Gold span và reference answer được rút còn 200 ký tự trong bảng. Phần accordion có đủ văn bản.
                """,
                best=errors["best_chunker"],
                n=len(errors["hard_misses"]),
            )
        )
        if errors["hard_misses"]:
            blocks.append(show_table([_table_row(item) for item in errors["hard_misses"]], label="Các miss khó"))
            blocks.append(
                mo.accordion(
                    {str(item["id"]): _detail(item, order) for item in errors["hard_misses"]}
                )
            )
        else:
            blocks.append(mo.md("Không có câu được chấm nào trên chunker tốt nhất có first_hit_rank null hoặc lớn hơn 3."))
        for title, rows in (
            ("Câu mọi chunker đều miss tại k=3", errors["all_miss_k3"]),
            ("Câu mọi chunker đều miss tại k=10", errors["all_miss_k10"]),
        ):
            blocks.append(md_fill("## {title}\n\n{n} câu.", title=title, n=len(rows)))
            if rows:
                cross = []
                for item in rows:
                    extra = {str(name) + "_rank": item["ranks"][name] for name in order}
                    cross.append(_table_row(item, extra))
                blocks.append(show_table(cross, label=title))
            else:
                blocks.append(mo.md("Không có."))
        blocks.append(
            md_fill(
                """
                ## Câu chỉ một chunker hit tại k=10

                {n} câu. Hit là `first_hit_rank` từ 1 đến 10.
                """,
                n=len(errors["only_one"]),
            )
        )
        if errors["only_one"]:
            only_rows = []
            for item in errors["only_one"]:
                extra = {"hit_chunker": item["hit_chunker"]}
                extra.update({str(name) + "_rank": item["ranks"][name] for name in order})
                only_rows.append(_table_row(item, extra))
            blocks.append(show_table(only_rows, label="Chỉ một chunker hit"))
            blocks.append(
                mo.accordion(
                    {
                        str(item["id"]): _detail(item, order)
                        for item in errors["only_one"]
                    }
                )
            )
        else:
            blocks.append(mo.md("Không có câu được chấm nào là hit của đúng một chunker tại k=10."))
        return mo.vstack(blocks)

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="conclusions"></a>

        # Kết luận
        """
    )
    return


@app.cell(hide_code=True)
def _(
    build_dataset,
    build_errors,
    build_generation,
    build_retrieval,
    build_review,
    fmt4,
    generation_report,
    kappa_band,
    md_fill,
    mo,
    recall_curve,
    review_report,
    run_rows,
    summaries,
    testset,
    top10_rows,
):
    def _join(names):
        quoted = ["`" + str(name) + "`" for name in names]
        if not quoted:
            return "không có"
        if len(quoted) == 1:
            return quoted[0]
        if len(quoted) == 2:
            return quoted[0] + " và " + quoted[1]
        return ", ".join(quoted[:-1]) + " và " + quoted[-1]

    def _lead(pairs):
        usable = [(name, value) for name, value in pairs if value is not None]
        if not usable:
            return None
        best_value = max(value for _, value in usable)
        best = [name for name, value in usable if round(float(value), 4) == round(float(best_value), 4)]
        rest = [(name, value) for name, value in usable if round(float(value), 4) != round(float(best_value), 4)]
        if not rest:
            return {"best": best, "best_value": best_value, "second": [], "second_value": None, "gap": 0.0}
        second_value = max(value for _, value in rest)
        second = [name for name, value in rest if round(float(value), 4) == round(float(second_value), 4)]
        return {
            "best": best,
            "best_value": best_value,
            "second": second,
            "second_value": second_value,
            "gap": best_value - second_value,
        }

    def _lead_sentence(metric, pairs):
        info = _lead(pairs)
        if info is None:
            return "Không có giá trị " + metric + " nào."
        if not info["second"]:
            return (
                "Mọi chunker có cùng "
                + metric
                + ", "
                + fmt4(info["best_value"])
                + " ("
                + _join(info["best"])
                + ")."
            )
        return (
            metric
            + " tốt nhất là "
            + _join(info["best"])
            + " với "
            + fmt4(info["best_value"])
            + ". Giá trị kế tiếp là "
            + fmt4(info["second_value"])
            + " ("
            + _join(info["second"])
            + "), chênh "
            + fmt4(info["gap"])
            + "."
        )

    def _weakest(groups):
        usable = []
        for name, block in groups.items():
            if block.get("n_scored") and block.get("mrr") is not None:
                usable.append((name, block["mrr"], block["n_scored"]))
        if not usable:
            return []
        worst = min(item[1] for item in usable)
        return [item for item in usable if round(float(item[1]), 4) == round(float(worst), 4)]

    def _render():
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        dataset = build_dataset(testset, review_report, summaries)
        review = build_review(review_report, testset)
        generation = build_generation(generation_report)
        errors = build_errors(summaries, run_rows, testset, review_report, top10_rows, recall_curve)
        if not retrieval["ok"]:
            return mo.md("Phần kết luận cần các file JSONL top-10. Các file đó chưa được đọc.")
        mrr_pairs = [(row["chunker"], row["mrr"]) for row in retrieval["rows"]]
        recall1 = [(row["chunker"], row["recall"].get("1")) for row in retrieval["rows"]]
        recall10 = [(row["chunker"], row["recall"].get("10")) for row in retrieval["rows"]]
        weak_lines = []
        small = []
        for row in retrieval["rows"]:
            weak_types = _weakest(row["by_type"])
            weak_docs = _weakest(row["by_doc"])
            type_text = (
                ", ".join(
                    "`" + str(name) + "` " + fmt4(value) + " (n_scored=" + str(n_scored) + ")"
                    for name, value, n_scored in weak_types
                )
                or "—"
            )
            doc_text = (
                ", ".join(
                    "`" + str(name) + "` " + fmt4(value) + " (n_scored=" + str(n_scored) + ")"
                    for name, value, n_scored in weak_docs
                )
                or "—"
            )
            weak_lines.append(
                "- `" + str(row["chunker"]) + "`: type yếu nhất theo MRR " + type_text + "; doc yếu nhất theo MRR " + doc_text + "."
            )
            for kind, groups in (("type", row["by_type"]), ("doc", row["by_doc"])):
                for name, block in groups.items():
                    if block.get("n_scored"):
                        small.append(block["n_scored"])
        mrr_info = _lead(mrr_pairs)
        spread = "—"
        if mrr_info is not None:
            low = min(value for _, value in mrr_pairs if value is not None)
            high = mrr_info["best_value"]
            low_names = [name for name, value in mrr_pairs if value is not None and round(float(value), 4) == round(float(low), 4)]
            spread = (
                "MRR chạy từ "
                + fmt4(low)
                + " ("
                + _join(low_names)
                + ") đến "
                + fmt4(high)
                + " ("
                + _join(mrr_info["best"])
                + "), chênh "
                + fmt4(high - low)
                + "."
            )
        r1_info = _lead(recall1)
        r10_info = _lead(recall10)
        recall_spread_bits = []
        for label, info, pairs in (("recall@1", r1_info, recall1), ("recall@10", r10_info, recall10)):
            if info is None:
                continue
            low = min(value for _, value in pairs if value is not None)
            recall_spread_bits.append(label + " chạy từ " + fmt4(low) + " đến " + fmt4(info["best_value"]) + ".")
        n_scored = (
            str(next(iter(set(retrieval["n_scored_values"].values()))))
            if retrieval["n_scored_agree"]
            else ", ".join(str(name) + "=" + str(value) for name, value in retrieval["n_scored_values"].items())
        )
        n_unanswerable = "—"
        unanswerable_values = {row["n_unanswerable"] for row in retrieval["rows"]}
        if len(unanswerable_values) == 1:
            n_unanswerable = str(next(iter(unanswerable_values)))
        min_group = min(small) if small else "—"
        discussion = len(review["discussion"]) if review["ok"] else "—"
        q_kappa = None
        s_kappa = None
        q_n = "—"
        if review["ok"]:
            q_block = review["agreement"].get("question_ok") or {}
            s_block = review["agreement"].get("span_ok") or {}
            q_kappa = q_block.get("fleiss_kappa")
            s_kappa = s_block.get("fleiss_kappa")
            q_n = q_block.get("n_overlap")
        backend = generation["backend"] if generation["ok"] else "—"
        hard_n = len(errors["hard_misses"]) if errors["ok"] else "—"
        all10 = len(errors["all_miss_k10"]) if errors["ok"] else "—"
        return md_fill(
            """
            {mrr_sentence} {recall1_sentence} {recall10_sentence}

            {spread} {recall_spread}

            Question type và document yếu nhất theo MRR, trong từng chunker (các nhóm unanswerable được bỏ vì không được chấm):

            {weak_lines}

            Các tỷ lệ này dùng n_scored = {n_scored}. Nhóm phân rã được chấm nhỏ nhất có n_scored = {min_group}, nên các nhóm nhỏ nhiễu. {n_unanswerable} câu accepted là unanswerable và không nằm trong MRR. {discussion} câu overlap vẫn nằm trong needs_discussion và không được chấm. Fleiss' kappa là {q_kappa} ({q_band}) trên question_ok và {s_kappa} ({s_band}) trên span_ok, với n_overlap = {q_n}. Câu hỏi được sinh bởi backend `{backend}`. Trên chunker có MRR tốt nhất, {hard_n} câu được chấm có first_hit_rank null hoặc lớn hơn 3, và {all10} câu được chấm bị mọi chunker miss tại k=10.
            """,
            mrr_sentence=_lead_sentence("MRR", mrr_pairs),
            recall1_sentence=_lead_sentence("recall@1", recall1),
            recall10_sentence=_lead_sentence("recall@10", recall10),
            spread=spread,
            recall_spread=" ".join(recall_spread_bits),
            weak_lines="\n".join(weak_lines),
            n_scored=n_scored,
            min_group=min_group,
            n_unanswerable=n_unanswerable,
            discussion=discussion,
            q_kappa="không xác định" if q_kappa is None else fmt4(q_kappa),
            q_band=kappa_band(q_kappa),
            s_kappa="không xác định" if s_kappa is None else fmt4(s_kappa),
            s_band=kappa_band(s_kappa),
            q_n=q_n,
            backend=backend,
            hard_n=hard_n,
            all10=all10,
        )

    _render()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a id="limitations-and-next-steps"></a>

        # Hạn chế và bước tiếp theo
        """
    )
    return


@app.cell(hide_code=True)
def _(
    build_dataset,
    build_generation,
    build_manifest,
    build_retrieval,
    build_review,
    fmt4,
    generation_report,
    kappa_band,
    manifest_text,
    md_fill,
    mo,
    recall_curve,
    review_report,
    run_rows,
    summaries,
    testset,
    top10_rows,
):
    def _render():
        manifest = build_manifest(manifest_text)
        generation = build_generation(generation_report)
        dataset = build_dataset(testset, review_report, summaries)
        review = build_review(review_report, testset)
        retrieval = build_retrieval(summaries, run_rows, top10_rows, recall_curve)
        if not dataset["ok"] or not retrieval["ok"]:
            return mo.md(
                "Các hạn chế có dẫn cỡ mẫu cần `testset.jsonl` và các file JSONL top-10. Hai nhóm file đó chưa được đọc đủ. Việc làm tiếp không phụ thuộc vào một con số: hybrid retrieval, reranker, thêm câu hỏi, và một vòng annotation thứ hai."
            )
        n_scored = (
            str(next(iter(set(retrieval["n_scored_values"].values()))))
            if retrieval["n_scored_agree"]
            else "các summary không thống nhất"
        )
        n_unanswerable = "—"
        values = {row["n_unanswerable"] for row in retrieval["rows"]}
        if len(values) == 1:
            n_unanswerable = str(next(iter(values)))
        small = []
        for row in retrieval["rows"]:
            for groups in (row["by_type"], row["by_doc"]):
                for block in groups.values():
                    if block.get("n_scored"):
                        small.append(block["n_scored"])
        min_group = min(small) if small else "—"
        overlap_size = review["overlap_size"] if review["ok"] else "—"
        discussion = len(review["discussion"]) if review["ok"] else "—"
        q_kappa = s_kappa = None
        q_n = "—"
        if review["ok"]:
            q_block = review["agreement"].get("question_ok") or {}
            s_block = review["agreement"].get("span_ok") or {}
            q_kappa = q_block.get("fleiss_kappa")
            s_kappa = s_block.get("fleiss_kappa")
            q_n = q_block.get("n_overlap")
        q_share = "chưa tính tỷ lệ nhãn"
        if review["ok"]:
            share = review["shares"]["question_ok"]
            if share["total"] and share["counts"]:
                label, votes = max(share["counts"].items(), key=lambda item: item[1])
                q_share = str(label) + " chiếm " + f"{(100.0 * votes / share['total']):.1f}%" + " số vote question_ok"
        embedding = manifest["embedding"] if manifest["ok"] and manifest["embedding"] else "không ghi"
        date_detail = manifest["date_detail"] if manifest["ok"] and manifest["date_detail"] else "không ghi"
        k_values = ", ".join(str(k) for k in retrieval["k_values"])
        backend = generation["backend"] if generation["ok"] else "—"
        drift_max = retrieval.get("summary_drift_max")
        if drift_max is None:
            drift_note = (
                "Các file top-10 là một lần retrieval in-process thứ hai trên cùng các câu hỏi. "
                "Model embedding chạy ở bfloat16 trên CPU, và các chunk gần hòa có thể đổi chỗ, "
                "nên lần chạy lại này có thể lệch nhẹ so với các file `*-accepted.summary.json` trước đó. "
                "Không có các file cũ đó để đếm khoảng lệch. Báo cáo này chỉ dùng các dòng top-10."
            )
        else:
            drift_note = (
                "Các file top-10 là một lần retrieval in-process thứ hai trên cùng các câu hỏi. "
                "Model embedding chạy ở bfloat16 trên CPU, và các chunk gần hòa có thể đổi chỗ. "
                "So với các file `*-accepted.summary.json` trước đó, số hit của recall@k lệch nhiều nhất "
                + str(drift_max)
                + " câu tại mỗi k được báo cáo. Báo cáo này chỉ dùng các dòng top-10, nên các bảng, đường cong và ví dụ là một phép đo. "
                "Các file summary trước đó lệch nhẹ và không được trộn vào các số này."
            )
        return md_fill(
            """
            - Tập được chấm có n_scored = {n_scored}. Các nhóm phân rã nhỏ tới n_scored = {min_group}, nên các tỷ lệ đó đổi nhiều nếu vài nhãn thay đổi.
            - {n_unanswerable} câu accepted không được chấm bởi recall@k hay MRR vì không có gold span. Một metric sau này có thể kiểm tra retriever có abstain trên chúng hay không.
            - Phần agreement dựa trên n_overlap = {overlap_size} (kappa dùng n_overlap = {q_n}). Fleiss' kappa là {q_kappa} ({q_band}) cho question_ok và {s_kappa} ({s_band}) cho span_ok. {q_share}, và kappa phạt sự lệch đó.
            - Hit là span containment trong một chunk được retrieve. Đó không phải đánh giá chất lượng câu trả lời.
            - Chỉ dùng một embedding model ({embedding}). Bảng chính dùng k = {k_values}. Đường recall vẽ k = 1..10. Câu hỏi được sinh bởi backend `{backend}`.
            - MANIFEST.md ghi ngày của snapshot summary trước đó ({date_detail}). recall@k và MRR trong báo cáo này được tính lại từ lần chạy top-10 sau đó.
            - {drift_note}
            - {discussion} câu vẫn nằm trong needs_discussion (`candidate`) và bị loại khỏi phần chấm cho đến khi reviewer chốt.
            - Hướng cải thiện có thể làm: hybrid retrieval, reranker, thêm câu hỏi, và một vòng annotation thứ hai trên các dòng chưa chốt và các câu mọi chunker đều miss.
            """,
            n_scored=n_scored,
            min_group=min_group,
            n_unanswerable=n_unanswerable,
            overlap_size=overlap_size,
            q_n=q_n,
            q_kappa="không xác định" if q_kappa is None else fmt4(q_kappa),
            q_band=kappa_band(q_kappa),
            s_kappa="không xác định" if s_kappa is None else fmt4(s_kappa),
            s_band=kappa_band(s_kappa),
            q_share=q_share,
            embedding=embedding,
            k_values=k_values,
            backend=backend,
            date_detail=date_detail,
            discussion=discussion,
            drift_note=drift_note,
        )

    _render()
    return


if __name__ == "__main__":
    app.run()
