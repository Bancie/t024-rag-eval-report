# T024 RAG eval report

Notebook marimo báo cáo đánh giá Retriever của doc-rag (recall@k, MRR) trên test set đã được người review. Notebook chỉ đọc file có sẵn trong repo, không gọi model, không dùng mạng.

## Xem trên molab

- Xem trước (không cần đăng nhập): https://molab.marimo.io/github/Bancie/t024-rag-eval-report/blob/main/rag_eval_report.py

## Chạy trên macOS (Python 3.11+)

```bash
git clone https://github.com/Bancie/t024-rag-eval-report.git
cd t024-rag-eval-report
python3 -m venv .venv && source .venv/bin/activate
pip install "marimo>=0.16" matplotlib
marimo edit rag_eval_report.py
```

## Cấu trúc

- `rag_eval_report.py` — notebook
- `data/` — test set đã review (`testset.jsonl`), `review_report.json`, `generation_report.json`, `candidates.jsonl`
- `results/` — kết quả retrieval; các số recall@k và MRR trong báo cáo tính lại từ `results/top10/*-top10.jsonl`

## Đóng góp

Fork repo, sửa notebook, mở PR. Nguồn gốc: `source-tool/rag-eval/report/` trong repo nội bộ của team T024; bản này đã chỉnh đường dẫn cho cấu trúc thư mục phẳng.
