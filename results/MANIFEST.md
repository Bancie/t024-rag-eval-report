# rag-eval results snapshot
- Date: 2026-10-17 (run 01:08-01:56 UTC+7), on CPU (8 vCPU), HF_HUB_OFFLINE=1
- Testset: data/testset_accepted.jsonl = rows with status == accepted from data/testset.jsonl (branch cursor/rag-eval-review-server, commit a62abd2): 113 rows, 82 scored, 31 unanswerable (no gold span, not scored)
- Embedding: Qwen/Qwen3-Embedding-0.6B via doc-rag CLI (Bancie/grok-bot-doc-rag @ 0078135)
- Runs: section-accepted, window-accepted, sentence-accepted (k = 1,3,5,10), review_status = reviewed
- Files: <run>.summary.json (overall, by_type, by_doc_id) and <run>.jsonl (per-question: id, question, type, doc_id, page, section, gold_span, status, scored, first_hit_rank)
