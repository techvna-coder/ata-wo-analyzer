# ATA Work Order Analyzer

Ứng dụng Streamlit xác định mã **ATA 4 ký tự** từ Work Orders hàng không, sử dụng phương pháp tam-đối-soát giữa dữ liệu nhập tay, tham chiếu TSM/FIM/AMM và suy luận từ mô tả hỏng hóc.

## Tính năng chính

- ✅ **Lọc Non-Defect**: Tự động loại bỏ WO không phải hỏng hóc kỹ thuật (routine, servicing, cleaning...)
- 🔍 **Trích xuất & xác thực tham chiếu**: Parse TSM/FIM/AMM từ hành động khắc phục, kiểm tra tồn tại trong registry
- 🎯 **Suy luận ATA Catalog (TF-IDF)**: Xác định ATA từ mô tả hỏng hóc bằng TF-IDF (không cần OpenAI API)
- 🤝 **Tam-đối-soát thông minh**: Kết hợp 3 nguồn (E0-E1-E2) với logic ra quyết định CONFIRM/CORRECT/REVIEW
- 📊 **Xuất Excel**: File kết quả với độ tin cậy và bằng chứng đầy đủ

## Kiến trúc

### Catalog Mode (Khuyến nghị - Mặc định)
```
SGML Manuals → build_ata_catalog.py → ATA Catalog (JSON + TF-IDF model)
                                              ↓
Work Orders → app.py → Catalog Inference → Decision Engine → Excel Output
```

### RAG Mode (Tùy chọn - Khi cần tra cứu sâu)
```
SGML Manuals → build_reference_index.py → DuckDB Registry + FAISS Index
                                                    ↓
Work Orders → app.py → Citation Validation + RAG Search → Decision → Output
```

## Cài đặt

### Yêu cầu
- Python 3.10+
- 8GB RAM (Catalog mode) / 16GB+ RAM (RAG mode với SGML lớn)

### Cài đặt dependencies

```bash
# Clone repository
git clone https://github.com/your-org/ata-wo-analyzer.git
cd ata-wo-analyzer

# Cài đặt packages cơ bản
pip install -r requirements.txt

# (Tùy chọn) Cài thêm cho RAG mode
pip install faiss-cpu duckdb langchain langchain-openai tiktoken
```

## Sử dụng

### Bước 1: Xây dựng ATA Catalog (Khuyến nghị)

```bash
python scripts/build_ata_catalog.py \
  --tar path/to/SGML_A320.tar \
  --manual-type TSM \
  --output catalog/
```

Tạo ra:
- `catalog/ata_catalog.json`: Định nghĩa hệ thống, từ khóa, cảnh báo theo ATA04
- `catalog/model/tfidf_vectorizer.pkl`: Model TF-IDF đã huấn luyện
- `catalog/model/tfidf_matrix.pkl`: Ma trận features

### Bước 2: (Tùy chọn) Xây dựng RAG Index

Chỉ cần khi muốn tra cứu chi tiết task/snippet từ manuals:

```bash
python scripts/build_reference_index.py \
  --tar path/to/SGML_A320.tar \
  --output-dir reference_db/ \
  --shard-size 5000
```

### Bước 3: Chạy ứng dụng

```bash
streamlit run app.py
```

Truy cập: http://localhost:8501

### Bước 4: Xử lý Work Orders

1. **Upload Excel WO**: File Excel với các cột bắt buộc (xem định dạng bên dưới)
2. **Cấu hình**: Chọn mode (Catalog/RAG), ngưỡng confidence
3. **Chạy xử lý**: Nhấn "Process Work Orders"
4. **Tải kết quả**: Download file `WO_ATA_checked.xlsx`

## Định dạng file Excel đầu vào

### Cột bắt buộc

| Tên cột file | Ánh xạ nội bộ | Mô tả |
|--------------|---------------|-------|
| ATA | ATA04_Entered | ATA do thợ máy nhập |
| W/O Description | Defect_Text | Mô tả hỏng hóc |
| W/O Action | Rectification_Text | Hành động khắc phục |
| Type | WO_Type | Loại WO (Pilot/Maint/Cabin...) |
| A/C | AC_Registration | Số đăng ký tàu bay |
| Issued | Open_Date | Ngày mở WO |
| Closed | Close_Date | Ngày đóng WO |
| ATA 04 Corrected | ATA04_Final | Cột kết quả (app ghi đè) |

### Cột khuyến nghị thêm
- **WO_Number**: Mã WO duy nhất (để audit/truy vết)

## Logic nghiệp vụ

### 1. Lọc Non-Defect (Pha 1)

**Loại trừ** nếu Description/Action chứa:
- cleaning, lubrication, servicing, oil replenishment
- first aid kit, tyre wear, scheduled maintenance
- software load, NFF (No Fault Found)

**Ngoại lệ** (vẫn coi là defect):
- Có từ khóa: failure, leak, overheat, vibration, ECAM, EICAS, CAS, fault, smoke, warning

### 2. Trích xuất & Xác thực Tham chiếu (E1)

**Pattern hỗ trợ**:
- TSM 21-26-00, TSM21-26, TSM212600
- FIM 32-00-00-860-801
- AMM 24-11-00

**Xác thực**: Tra cứu DuckDB registry (nếu đã build) để đánh dấu `Cited_Exists=True/False`

### 3. Suy luận từ Catalog/RAG (E2)

**Catalog mode**:
- TF-IDF similarity giữa defect text và catalog descriptions
- Top-1 ATA04 với score > 0.2

**RAG mode**:
- Tìm kiếm FAISS trong TSM → FIM → AMM
- Trích xuất ATA04 từ top-3 chunks

### 4. Tam-đối-soát & Quyết định

| Điều kiện | Quyết định | Confidence | ATA04_Final |
|-----------|------------|------------|-------------|
| E0=E1=E2 (E1 valid) | CONFIRM | 0.97 | E0 |
| E1=E2≠E0 (E1 valid) | CORRECT | 0.95 | E1 |
| E2=E0, E1 missing | CONFIRM | 0.83-0.88 | E0 |
| Only E1 valid | CONFIRM | 0.92 | E1 |
| E1≠E2 | Chọn mạnh hơn / REVIEW | 0.75-0.85 | E1 or E2 |
| Only E0 | REVIEW | 0.65 | E0 |

## Cấu hình nâng cao

### File `.env` (Tùy chọn cho RAG)

```env
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Tùy chỉnh Non-Defect patterns

Chỉnh sửa `core/non_defect_filter.py`:

```python
NON_DEFECT_PATTERNS = [
    r'\bclean(?:ing|ed)?\b',
    r'\blubrication\b',
    # Thêm patterns khác...
]
```

## Hiệu năng

| Mode | Tốc độ | RAM | API Cost |
|------|--------|-----|----------|
| Catalog | ~20k WO trong 1-3 phút | 2-4GB | $0 |
| RAG (query) | ~20k WO trong 5-10 phút | 4-8GB | ~$0.5-2 |
| RAG (build index) | Phụ thuộc SGML size | 8-16GB | ~$5-50 |

## Kiểm soát chất lượng

### KPI đề xuất
- **Accuracy**: ≥90% trên tập validation được gán nhãn thủ công
- **REVIEW rate**: ≤10%, giảm dần khi tinh chỉnh catalog
- **Processing time**: ≤5 phút cho 20k WO (Catalog mode)

### Validation checklist
- [ ] ATA04 format: `AA-BB` hoặc `AA-BB-CC`
- [ ] Dates hợp lệ (Issued < Closed)
- [ ] Description không rỗng
- [ ] Catalog đã build thành công
- [ ] Test với sample 100 WO trước khi chạy full

## Troubleshooting

### Lỗi: "Catalog not found"
```bash
# Chạy lại build catalog
python scripts/build_ata_catalog.py --tar SGML.tar --manual-type TSM
```

### Lỗi: "Memory error khi build RAG"
```bash
# Giảm shard size
python scripts/build_reference_index.py --shard-size 2000
```

### Lỗi: "OpenAI rate limit"
```bash
# Build với batch size nhỏ hơn
python scripts/build_reference_index.py --batch-size 50 --retry 5
```

## Roadmap

- [ ] Fuzzy validation cho cited references
- [ ] Multi-fleet catalog support
- [ ] LLM extraction cho edge cases
- [ ] Web API deployment
- [ ] CI/CD với unit tests

## Đóng góp

Mọi đóng góp đều được hoan nghênh! Vui lòng:
1. Fork repository
2. Tạo branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

## License

MIT License - xem file LICENSE

## Liên hệ

- **Issue tracker**: https://github.com/your-org/ata-wo-analyzer/issues
- **Documentation**: https://docs.your-org.com/ata-wo-analyzer

---

**Lưu ý bảo mật**: Không commit file `.env` hoặc dữ liệu WO thực lên repository công khai.