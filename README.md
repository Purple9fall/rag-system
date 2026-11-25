# RAG System

Hệ thống RAG xử lý tài liệu bằng **Docling / Unstructured / Apache Tika**, chunk và sinh câu trả lời bằng **LlamaIndex**, lưu trữ bằng **Qdrant** (vector database) và **PostgreSQL** (relational database). Truy xuất theo dạng **phễu**: `filter → hybrid search → rerank`.

## Kiến trúc

```
                        COLLECTION (tùy chọn)
API học thuật / trang tài liệu ──► tìm kiếm, lọc, chấm điểm
                              ──► data/raw/<topic>/ + data/metadata/*.jsonl

                         INGEST
 file ──► parser (Docling → Unstructured → Tika, có fallback)
      ──► chunk (MarkdownNodeParser → SentenceSplitter, LlamaIndex)
      ──► encode (dense bge-m3 + sparse BM25)
      ──► PostgreSQL: documents + chunks (metadata, nội dung)
      ──► Qdrant   : dense + sparse vector, payload {doc_id, chunk_index}

                         QUERY (phễu)
 câu hỏi
   │
   ▼  Tầng 1 · FILTER   PostgreSQL lọc theo metadata → tập doc_id
   │                    (file_type, language, tags, file_name, khoảng thời gian)
   ▼  Tầng 2 · HYBRID   Qdrant dense + sparse, hợp nhất bằng RRF, chỉ trong tập doc_id
   │                    → top HYBRID_TOP_K chunk
   ▼  Tầng 3 · RERANK   Cross-encoder chấm lại (query, chunk) → top FINAL_TOP_K
   │
   ▼  Generation        LlamaIndex LLM trả lời, trích dẫn nguồn [n]
```

Phân vai hai database:

| Database | Lưu gì | Dùng ở đâu |
| --- | --- | --- |
| PostgreSQL | `documents` (metadata), `chunks` (nội dung văn bản) | Tầng 1 (filter), lấy nội dung chunk cho tầng 3 và generation |
| Qdrant | Dense vector, sparse vector, payload `doc_id` | Tầng 2 (hybrid search) |

`chunks.id` trong PostgreSQL trùng với point id trong Qdrant.

## Cấu trúc thư mục

```
rag-system/
├── README.md
├── pyproject.toml            # dependencies, cài bằng pip install -e .
├── docker-compose.yml        # PostgreSQL + Qdrant
├── .env.example              # copy thành .env
├── sql/schema.sql            # bảng documents, chunks, index
├── configs/collection/       # nguồn, điều kiện, scoring, chủ đề
├── data/
│   ├── raw/                  # tài liệu theo chủ đề
│   ├── metadata/             # documents.jsonl, collection_log.jsonl
│   ├── temp/
│   └── processed/
├── scripts/
│   ├── init_db.py            # tạo schema + collection
│   ├── ingest.py             # nạp file hoặc collection manifest
│   ├── query.py              # hỏi đáp, hỗ trợ lọc collection/topic
│   ├── collect_data.py       # chạy collection
│   └── evaluate_rag.py       # đánh giá retrieval
├── src/collection/           # tìm kiếm, crawl, tải, lọc, chấm điểm, metadata
├── src/ingestion/            # điều phối ingest corpus
├── src/retrieval/            # truy xuất và đánh giá corpus
├── src/rag/
│   ├── config.py             # đọc cấu hình từ .env
│   ├── models.py             # SearchFilters, Candidate, FunnelResult...
│   ├── factory.py            # lắp các thành phần
│   ├── ingestion/
│   │   ├── parsers.py        # Docling / Unstructured / Tika + fallback
│   │   ├── chunker.py        # LlamaIndex node parsers
│   │   └── pipeline.py       # Ingestor (dedup bằng sha256, đồng bộ 2 DB)
│   ├── embeddings/encoders.py    # dense (sentence-transformers) + sparse (fastembed BM25)
│   ├── storage/
│   │   ├── relational.py     # PostgresStore
│   │   └── vector.py         # QdrantStore (hybrid + RRF)
│   ├── retrieval/
│   │   ├── funnel.py         # phễu filter → hybrid → rerank
│   │   └── reranker.py       # CrossEncoderReranker
│   ├── generation/answer.py  # prompt + LlamaIndex LLM
│   └── api/main.py           # FastAPI
└── tests/test_funnel.py      # test logic phễu bằng fake store
```

## Yêu cầu

- Python 3.10 trở lên
- Docker (cho PostgreSQL và Qdrant)
- Java 8 trở lên (Apache Tika)
- Một LLM API key (OpenAI hoặc dịch vụ tương thích OpenAI, xem mục "Dùng API và database miễn phí")

## Cài đặt và chạy

```bash
# 1. Môi trường
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Cấu hình
cp .env.example .env        # sửa OPENAI_API_KEY, các tham số khác nếu cần

# 3. Database
docker compose up -d
python scripts/init_db.py

# 4. Nạp tài liệu
cp /duong/dan/tai-lieu/* data/raw/
python scripts/ingest.py data/raw --tags hop-dong 2025 --language vi

# 5. Hỏi đáp
python scripts/query.py "Điều khoản thanh toán là gì?"
python scripts/query.py "Điều khoản thanh toán là gì?" --file-type pdf --tag hop-dong --after 2025-01-01
python scripts/query.py "Điều khoản thanh toán là gì?" --no-answer     # chỉ xem kết quả truy xuất
```

Lần chạy đầu sẽ tải model (bge-m3, bge-reranker-v2-m3, BM25) và Docling tải model layout/OCR, nên mất thời gian.

### Thu thập tài liệu PIC bằng crawler

Crawler cho collection `01_photonicICfundamental` có 11 topic trong `configs/collection/topics/`. Nguồn, điều kiện lọc, giới hạn request và điểm chọn tài liệu nằm trong bốn file YAML dùng chung ở `configs/collection/`. Crawler dùng `urllib` để tải và BeautifulSoup để đọc HTML. **Crawl và ingestion là hai bước riêng:** `collect_data.py` không tạo embedding, không kết nối PostgreSQL/Qdrant và không tự gọi `ingest.py`. Bạn có thể thử crawl trước khi khởi động database hoặc cấu hình LLM.

Sau khi cài project bằng `pip install -e .` như ở trên, đặt email liên hệ cho User-Agent trong môi trường shell. `collect_data.py` không tự đọc biến này từ `.env`:

```bash
export CRAWLER_CONTACT_EMAIL='you@example.com'
python scripts/collect_data.py --topic pic_fundamentals --dry-run
```

`--dry-run` vẫn gửi request và có thể tải nội dung vào bộ nhớ, nhưng không ghi file, manifest hoặc log. Khi kết quả phù hợp, chạy thật:

```bash
python scripts/collect_data.py --topic pic_fundamentals
python scripts/collect_data.py --topic mmi_coupler --topic mmi_geometry  # nhiều topic
python scripts/collect_data.py                                      # cả 11 topic
```

Kết quả in ra là JSON: `discovered` là số ứng viên, `selected` là số đạt điều kiện và điểm tối thiểu, `saved` là số bản ghi/topic mới trong manifest, `downloaded` là số bản ghi có toàn văn được xử lý, `skipped` là số bị bỏ qua và `failed` là số lỗi được cộng vào thống kê. Với `--dry-run`, `saved` và `downloaded` chỉ là số dự kiến vì không có file nào được ghi. **`saved` không đồng nghĩa có file**: Crossref hiện chỉ cung cấp metadata, nên có thể thấy `saved: 7, downloaded: 0`. Một số lỗi ở từng trang chỉ hiện thành `WARNING` trên terminal. Chạy lại sẽ dùng manifest để bỏ qua các bản ghi đã có; không cần xóa dữ liệu cũ.

Tài liệu PDF/HTML được lưu ở `data/raw/<topic>/`; `pic_fundamentals` có thêm các thư mục `architecture`, `waveguides`, `propagation`, `modes`, `mode_interaction`. Metadata và log từng lượt nằm ở `data/metadata/documents.jsonl` và `data/metadata/collection_log.jsonl`. Hai file JSONL chỉ xuất hiện sau khi chạy thật. Kiểm tra kết quả bằng:

Một lượt chạy tất cả topic không bảo đảm mọi thư mục `raw` đều có file: Crossref chỉ lưu metadata, còn arXiv/Ansys phải trả được toàn văn và tài liệu phải vượt qua bộ lọc. Crawler cảnh báo những topic chưa có tài liệu toàn văn. Nếu một tài liệu phù hợp với nhiều topic, crawler dùng lại nội dung trong từng thư mục topic.

```bash
find data/raw -type f ! -name .gitkeep | sort
tail -n 3 data/metadata/collection_log.jsonl
```

Nguồn Ansys chỉ áp dụng cho một số topic kỹ thuật, không dùng cho `pic_fundamentals`. Nếu host trả HTTP 403, crawler dừng gọi host đó trong lượt chạy. arXiv dùng endpoint API công khai với khoảng cách tối thiểu 3 giây giữa các request; URL PDF vẫn qua kiểm tra `robots.txt`. OpenAlex mặc định tắt. Nếu `downloaded` bằng 0, xem các dòng `WARNING Discovery failed for arxiv/...` trước khi thay đổi config.

Khi đã có file toàn văn và muốn nạp chúng vào RAG, khởi động PostgreSQL/Qdrant, chạy `scripts/init_db.py` theo hướng dẫn ở trên, rồi gọi ingestion riêng:

```bash
python scripts/ingest.py --collection --topic pic_fundamentals
python scripts/query.py 'What is an optical waveguide mode?' --collection --topic pic_fundamentals
```

`ingest.py --collection` chỉ nạp các bản ghi có `file_path` trong manifest; bản ghi chỉ có metadata sẽ không được nạp. Bỏ `--topic` để nạp tất cả topic. Lịch trong `settings.yaml` chưa được nối với scheduler; các lệnh crawl hiện chạy thủ công.

Mỗi dòng của bộ đánh giá JSONL cần `question` và `relevant_files` (danh sách tên file từ manifest), có thể thêm `topic_id`. Ví dụ:

```json
{"question":"How does self imaging work in an MMI coupler?","topic_id":"mmi_coupler","relevant_files":["<sha256>.pdf"]}
```

```bash
python scripts/evaluate_rag.py path/to/questions.jsonl --top-k 5 --output data/processed/01_photonicICfundamental/evaluation.json
```

Kết quả đánh giá gồm hit rate@k và MRR@k. Cấu hình lịch trong `settings.yaml` là thông số cho scheduler sẽ tích hợp sau; chạy các script trên là thủ công.

### API

```bash
uvicorn rag.api.main:app --reload

curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{
  "question": "Điều khoản thanh toán là gì?",
  "filters": {"file_types": ["pdf"], "tags": ["hop-dong"]},
  "top_k": 5
}'
```

Response gồm `answer`, `stats` (số tài liệu sau filter, số chunk hybrid, thời gian từng tầng) và `sources`.

## Cấu hình (`.env`)

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://rag:rag@localhost:5432/rag` | Kết nối PostgreSQL |
| `QDRANT_URL`, `QDRANT_API_KEY` | `http://localhost:6333`, trống | Kết nối Qdrant |
| `QDRANT_COLLECTION` | `rag_chunks` | Tên collection |
| `DENSE_MODEL`, `DENSE_DIM` | `BAAI/bge-m3`, `1024` | Model dense và số chiều. Đổi model thì phải đổi `DENSE_DIM` và tạo lại collection |
| `SPARSE_MODEL` | `Qdrant/bm25` | Model sparse của fastembed |
| `RERANK_MODEL`, `ENABLE_RERANK` | `BAAI/bge-reranker-v2-m3`, `true` | Cross-encoder; đặt `false` để bỏ tầng 3 |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | `512`, `64` | Kích thước chunk (token) |
| `HYBRID_TOP_K` | `50` | Số chunk giữ lại sau tầng 2 |
| `FINAL_TOP_K` | `5` | Số chunk cuối cùng đưa vào LLM |
| `LLM_MODEL` | `gpt-4o-mini` | LLM của LlamaIndex |
| `DEFAULT_LANGUAGE` | `vi` | Ngôn ngữ gán cho tài liệu khi không truyền `--language` |
| `DEVICE` | trống | `cpu`, `cuda`, `mps` |

## Dùng API và database miễn phí

Phần này hướng dẫn thay Docker local bằng dịch vụ cloud miễn phí và dùng LLM miễn phí. Các gói miễn phí và tên model đổi thường xuyên, hãy kiểm tra lại trên trang của từng nhà cung cấp.

### 1. LLM (API key)

1. Lấy key: Groq (console.groq.com), Google AI Studio (aistudio.google.com/apikey) hoặc Mistral (console.mistral.ai).
2. Mở `.env`, điền ba biến:

```env
# Groq
LLM_API_BASE=https://api.groq.com/openai/v1
LLM_API_KEY=dan-key-vao-day
LLM_MODEL=openai/gpt-oss-120b

# Gemini (chép đúng model ID từ AI Studio)
# LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/
# LLM_API_KEY=dan-key-vao-day
# LLM_MODEL=<model-id>
```

3. Cài thêm gói: `pip install -e .` (đã có `llama-index-llms-openai-like` trong `pyproject.toml`).
4. Thử: `python scripts/query.py "câu hỏi"`.

Gói miễn phí có giới hạn token mỗi phút. Nếu gặp lỗi 429, giảm `FINAL_TOP_K` trong `.env` hoặc đổi sang model/nhà cung cấp khác. Một số gói miễn phí cho phép nhà cung cấp dùng prompt để cải thiện sản phẩm, vì vậy không dùng cho tài liệu mật.

### 2. Qdrant Cloud (API key)

1. Đăng ký tại cloud.qdrant.io, tạo cluster gói Free.
2. Sao chép Cluster URL và tạo API key trong dashboard.
3. Điền vào `.env`:

```env
QDRANT_URL=https://xxxx.region.cloud.qdrant.io
QDRANT_API_KEY=dan-api-key-vao-day
```

4. Chạy `python scripts/init_db.py` để tạo collection trên cluster.

### 3. PostgreSQL miễn phí (chuỗi kết nối)

1. Tạo project tại neon.com (hoặc Supabase), sao chép connection string trong dashboard.
2. Điền vào `.env`, giữ nguyên `?sslmode=require`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
```

3. Nên dùng chuỗi kết nối trực tiếp (không có `-pooler` trong hostname) để chạy `init_db.py`.
4. Chạy `python scripts/init_db.py`, sau đó `ingest.py` và `query.py` như bình thường.

Lưu ý bảo mật: không commit file `.env` (đã nằm trong `.gitignore`), không dán key vào chat hay issue. Nếu lộ key, thu hồi và tạo key mới.

## Quyết định thiết kế

- **Filter trước, vector sau.** Tầng 1 thu hẹp phạm vi bằng SQL rồi truyền `doc_id` xuống Qdrant dưới dạng payload filter, nên hybrid search chỉ chạy trên tập đã lọc. Nếu filter trả về rỗng, phễu dừng ngay và không gọi Qdrant.
- **Hybrid bằng RRF phía Qdrant.** Dense và sparse được prefetch song song rồi hợp nhất bằng Reciprocal Rank Fusion, không cần tự chuẩn hóa điểm.
- **Nội dung chunk nằm ở PostgreSQL**, Qdrant chỉ giữ vector và id. Cách này giữ payload Qdrant nhỏ và cho phép sửa hoặc xóa nội dung tại một nơi.
- **Dedup bằng sha256.** File đã nạp sẽ bị bỏ qua, dùng `--force` để nạp lại.
- **Đồng bộ hai DB.** Ghi PostgreSQL trước, rồi Qdrant; nếu Qdrant lỗi thì xóa bản ghi PostgreSQL vừa ghi.
- **Chuỗi parser có fallback.** Docling cho PDF/Office/ảnh, Unstructured cho định dạng còn lại, Tika là phương án cuối.

## Hạn chế cần biết

- **BM25 và tiếng Việt.** Model `Qdrant/bm25` của fastembed mặc định dùng stemmer tiếng Anh và không tách từ tiếng Việt, nên nhánh sparse kém hơn nhánh dense với tiếng Việt. Muốn tốt hơn, tách từ trước (ví dụ underthesea, pyvi) hoặc dùng sparse của bge-m3.
- **Danh sách `doc_id` lớn.** Filter trả về hàng chục nghìn tài liệu sẽ làm payload filter của Qdrant nặng. Khi đó nên lưu thêm các trường lọc (file_type, tags...) vào payload Qdrant và lọc trực tiếp ở đó.
- **Kết nối PostgreSQL mở theo từng thao tác**, chưa dùng connection pool.
- **Không có ACL.** Chưa có phân quyền theo người dùng.
- **Chưa kiểm thử với dịch vụ thật.** Mới chạy unit test cho logic phễu (`pytest`) với store giả. Chưa chạy đầu-cuối với PostgreSQL, Qdrant và model thật. API của Docling, Unstructured, qdrant-client và fastembed đổi theo phiên bản, nếu gặp lỗi import hoặc tham số thì kiểm tra lại phiên bản.

## Kiểm thử

```bash
pytest
```
