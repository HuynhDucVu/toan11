# Hướng dẫn lập trình phần mềm quản lý ngân hàng đề thi LaTeX

Tài liệu này hướng dẫn từng bước xây dựng một phần mềm quản lý ngân hàng đề thi Toán
viết bằng LaTeX (khung `ex_test`). Các chức năng chính giống nhóm phần mềm kiểu MyLT:

* nhập câu hỏi từ file `.tex`;
* phân loại theo ID `[0D2N1-2]`;
* lọc và tìm kiếm câu hỏi;
* phát hiện câu trùng;
* sinh đề theo ma trận, trộn câu và trộn phương án;
* xuất nhiều mã đề, file lời giải và bảng đáp án.

> **Lưu ý.** Mã nguồn của MyLT không được công bố, và phần mềm đó thuộc về tác giả của nó.
> Vì vậy phần mềm ở đây được **viết lại từ đầu**: chức năng tương tự, nhưng không sao chép
> giao diện hay mã của MyLT. Nếu MyLT có chức năng nào chưa có ở đây, xem mục 11 (đối chiếu) và mục 12 (hướng phát triển).

Mã nguồn hoàn chỉnh nằm trong thư mục `nganhangde/` và chạy được ngay.

---

## 1. Chọn công nghệ

| Thành phần | Lựa chọn | Lí do |
|---|---|---|
| Ngôn ngữ | Python 3.10+ | Dễ học, xử lí chuỗi tốt, chạy trên Windows, macOS và Linux |
| Cơ sở dữ liệu | SQLite (`sqlite3` có sẵn) | Mỗi kho chỉ là một file `.db`, không cần cài máy chủ, dễ sao lưu và chép qua USB |
| Giao diện | PySide6 (Qt) | Giao diện hiện đại; cài bằng `pip`; đóng gói exe dễ. Bản Tkinter (`gui.py`) được giữ làm dự phòng |
| Đầu ra | File `.tex` + `.csv` | Thầy/cô biên dịch đề bằng `xelatex`/`pdflatex` với gói `ex_test` đang dùng |
| Đóng gói | PyInstaller | Tạo file `.exe` để chạy trên máy không cài Python |

## 2. Kiến trúc

```
nganhangde/
├── texutil.py    # Bước 1: đọc nhóm {...} cân bằng, bỏ qua comment và \{ \}
├── idcode.py     # Bước 2: giải mã ID 0D2N1-2 → lớp, môn, chương, mức độ, bài, dạng
├── parser.py     # Bước 3: tách \begin{ex}...\end{ex} → đối tượng Question
├── db.py         # Bước 4: lưu, tìm, lọc trong SQLite; chống trùng bằng mã băm
├── generator.py  # Bước 5: chọn câu theo ma trận, trộn câu, trộn phương án, tạo mã đề
├── exporter.py   # Bước 6: điền vào file mẫu .tex, xuất đề, lời giải và đáp án .csv
├── tools.py      # công cụ trên file .tex: lọc ID, tìm trùng, xoá lời giải, đổi ID, lấy đáp án, trộn file
├── idmap.py      # đọc/ghi Map ID (định dạng gạch ngang và «khoá = tên»), cây chọn ID
├── idsuggest.py  # gợi ý ID: câu giống trong kho (TF-IDF) + tên chương/bài/dạng trong Map ID
├── review.py     # rà soát đáp án – lời giải – LaTeX, tự sửa, xoá câu sai
├── tnmaker.py    # xuất đáp án Excel cho phần mềm chấm phiếu (TNMaker…)
├── omr.py        # phiếu chấm: sức chứa phiếu 2025, điền file mẫu đáp án bất kì, mã QR đáp án
├── scoring.py    # thang điểm tuỳ chỉnh (Phần I–IV)
├── matrix.py     # ma trận CV 7991: Excel/Word ↔ dòng ma trận
├── htmlconv.py   # LaTeX → HTML (giữ công thức cho MathJax)
├── online.py     # bài làm online (HTML tự chấm) và Moodle XML
├── wordconv.py   # Word ↔ LaTeX qua pandoc
├── mathgen.py    # sinh câu hỏi số từ câu mẫu có tham số
├── drawgen.py    # mã TikZ: bảng biến thiên, đồ thị, biểu đồ cột/quạt
├── pdfbuild.py   # biên dịch PDF: tìm MiKTeX/TeX Live, chạy nhiều lượt, đọc lỗi từ .log
├── aiid.py       # gán ID bằng Google Gemini (REST, không cần thư viện ngoài)
├── updater.py    # tự cập nhật: đọc Releases trên GitHub, tải exe, kiểm tra SHA-256, thay exe
├── editor.py     # mở file .tex bằng TeXstudio (nhảy tới dòng lỗi)
├── templates/nhd_extest.sty   # gói ex_test rút gọn dùng khi máy chưa cài ex_test
├── cli.py        # Bước 7a: dòng lệnh
├── textnorm.py   # bỏ dấu tiếng Việt, tạo truy vấn FTS5 («tap nghiem» tìm được «tập nghiệm»)
├── data/map_id_toan_6_12.tex  # danh mục ID có sẵn Toán 6–12 (1 504 mục)
├── ui/           # Bước 7b: giao diện chính (PySide6/Qt), mỗi file < 40 KB
│   ├── common.py, app.py, workers.py (QThread), main_window.py, bank_actions.py
│   ├── tabs/     # generator, exam_options, review, make_question, draw, tools, stats
│   └── dialogs/  # edit, swap, result, idmap, assign_id, ai_settings, update, pdf
├── gui_qt.py     # lớp tương thích: re-export mọi tên từ ui/ (mã cũ vẫn chạy)
├── gui.py        #          giao diện dự phòng (Tkinter)
├── assets/       # biểu tượng app.ico, app.png
└── templates/de_thi.tex   # file mẫu đề (thay bằng mẫu của trường)
run_gui.py        # điểm chạy khi đóng gói exe (có --selftest)
build_exe.bat     # nhấp đúp trên Windows → dist\NganHangDe.exe
.github/workflows/build-exe.yml   # GitHub tự đóng gói exe
```

Luồng dữ liệu:

```
file .tex ──parser──▶ Question ──db──▶ nganhang.db ──generator──▶ các mã đề ──exporter──▶ de_101.tex, loigiai_101.tex, dap_an.csv
```

## 3. Bước 1: đọc cấu trúc LaTeX (`texutil.py`)

Không thể tách `\choice{..}{..}{..}{..}` bằng biểu thức chính quy (regex), vì các phương án
chứa ngoặc lồng nhau như `$\dfrac{1}{2}$` hay `\left\{ \right\}`. Cách làm là **đếm độ sâu ngoặc**:

```python
def read_group(s, i):            # s[i] == "{"
    depth = 0; j = i
    while j < len(s):
        c = s[j]
        if c == "\\": j += 2; continue          # bỏ qua \{ \} \% \\
        if c == "%":  j = s.find("\n", j) + 1; continue   # bỏ qua comment
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return s[i+1:j], j+1
        j += 1
```

`read_command_args` gọi `read_group` nhiều lần liên tiếp. Nhờ vậy nó đọc được `\choice[1]{A}{B}{C}{D}`,
`\choiceTF[t]{..}{..}{..}{..}` và `\shortans[oly]{12}`.

## 4. Bước 2: mã ID (`idcode.py`)

ID có dạng `[0D2N1-2]`. Mỗi kí tự mang một ý nghĩa:

| Vị trí | Ý nghĩa | Giá trị |
|---|---|---|
| 1 | Lớp | `0` → 10, `1` → 11, `2` → 12 |
| 2 | Phân môn | `D` Đại số và Giải tích, `H` Hình học |
| 3 | Chương | `0`–`9`, `A`–`Z` |
| 4 | Mức độ | `N`/`Y` Nhận biết, `H`/`B` Thông hiểu, `V`/`K` Vận dụng, `C`/`G` Vận dụng cao |
| 5 | Bài | |
| sau `-` | Dạng | |

Mã ID được kiểm tra bằng một regex, rồi tách thành các cột riêng trong cơ sở dữ liệu
để lọc nhanh. Hai kiểu kí hiệu mức độ (N/H/V/C và Y/B/K/G) được **chuẩn hoá** về N/H/V/C.
Nhờ vậy, kho trộn lẫn hai kiểu ID vẫn thống kê đúng.

## 5. Bước 3: tách câu hỏi (`parser.py`)

1. Tìm mọi khối `\begin{ex}...\end{ex}` (và `bt` cho tự luận).
2. Đọc dòng đầu của khối để lấy các nhãn `%[...]`. Nhãn nào hợp lệ theo `parse_id` là **ID**;
   các nhãn còn lại (nguồn, tác giả) được lưu vào `tags`.
3. Cắt `\loigiai{...}` ra thành **lời giải**.
4. Xác định loại câu:
   * có `\choiceTF` → **DS** (đúng/sai);
   * có `\choice` → **TN** (trắc nghiệm);
   * có `\shortans` → **KQ** (trả lời ngắn);
   * không có cái nào → **TL** (tự luận).
5. Với mỗi phương án, `strip_true` bỏ chữ `\True` ở đầu và ghi lại phương án đó là đúng hay sai.
6. `Question.to_latex()` làm ngược lại: dựng lại khối LaTeX từ các trường.
   Hàm này dùng sau khi đã trộn phương án.

`validate()` soát các lỗi soạn thảo hay gặp:

* câu thiếu ID;
* câu TN không đủ 4 phương án, hoặc không có đúng 1 `\True`;
* câu trả lời ngắn không có đáp án;
* câu chưa có lời giải;
* số dấu `$` lẻ.

## 6. Bước 4: cơ sở dữ liệu (`db.py`)

Bảng `questions` có các cột lấy từ ID (`lop, mon, chuong, muc_do, bai, dang`) và nội dung câu:

* `stem` (đề bài), `choices` và `correct` (dạng JSON), `solution` (lời giải);
* `raw`: khối LaTeX gốc;
* `used_count`: số lần câu đã được đưa vào đề;
* `fingerprint UNIQUE`: dùng để **chống trùng**.

`fingerprint` là mã băm SHA-1 của nội dung đã chuẩn hoá:

* bỏ khoảng trắng, `$` và `{}`;
* bỏ `\left`, `\right`;
* đổi `\dfrac` thành `frac`;
* viết thường toàn bộ.

Hai câu chỉ khác nhau về cách gõ thì vẫn bị nhận ra là trùng.
`search()` lọc bằng SQL. Mẫu ID dùng `GLOB`, ví dụ `0D2?1-*` hay `0D[08]*`.

**Nâng cấp lược đồ (migration).** Phiên bản lược đồ lưu trong `PRAGMA user_version` (`SCHEMA_VERSION = 2`).
Khi mở kho cũ có dữ liệu, `Bank._migrate()` sao lưu nguyên file thành `nganhang.db.bak` (API backup của SQLite)
rồi chạy lần lượt `_migrate_v2`… Mỗi bước chỉ *thêm* cột/bảng, không xoá dữ liệu:

* cột `choice_cmd` (giữ đúng lệnh `\choiceTF`/`\choiceTFt`/`\shortans`/`\dapso` khi xuất lại),
  `group_id` (câu chùm, lấy từ thẻ `%[chum:TÊN]`), `search_text` (nội dung đã bỏ dấu);
* bảng ảo **FTS5** `questions_fts` (external content) + 3 trigger giữ đồng bộ → tìm kiếm không dấu, rất nhanh.
  Máy nào SQLite thiếu FTS5 thì tự quay về `LIKE`;
* `exam_batches`, `exam_items`: **lịch sử ra đề** (đợt nào, mã đề nào, câu nào ở vị trí nào).
  `recent_question_ids(N)` cho phép tránh lặp câu giữa N bài kiểm tra gần nhất;
* `assets`: ảnh/hình gắn với câu hỏi.

## 7. Bước 5: sinh đề và trộn đề (`generator.py`)

**Ma trận** là danh sách các dòng `Rule(qtype, count, id, muc_do)`. Ví dụ:
`Rule("TN", 6, "0H9*")` nghĩa là lấy 6 câu trắc nghiệm thuộc chương 9 phần Hình.
Mỗi dòng được xử lí như sau:

1. Lấy các câu thoả điều kiện, bỏ những câu đã được dòng trước chọn.
2. Nếu không đủ câu thì báo lỗi rõ dòng nào thiếu bao nhiêu câu.
3. Xáo trộn ngẫu nhiên. Nếu bật «ưu tiên câu ít dùng» thì sắp xếp theo `used_count`.
4. Lấy `count` câu đầu tiên.

**Trộn đề:**

* Mỗi mã đề dùng `random.Random(seed)`. Cùng một `seed` thì sinh lại đúng bộ đề cũ.
* *Trộn câu* là xáo thứ tự câu **trong từng phần** (I, II, III, IV).
* *Trộn phương án TN* dùng một hoán vị `perm`, áp đồng thời cho `choices` và `correct`.
  Vì `\True` đi theo phương án, đáp án luôn đúng.
* *Trộn ý câu Đúng/Sai* còn phải đổi thứ tự các mục `\itemch` trong lời giải theo cùng `perm`.
  Nếu không tách được lời giải thì giữ nguyên thứ tự ý cho an toàn.
* *Không trộn phương án* khi có phương án kiểu «Cả A, B đều đúng» hay «Tất cả đều sai»
  (xem `LOCK_RE`).

* *Cân bằng đáp án:* với mỗi mã đề, các vị trí đích A, B, C, D được lặp đều rồi xáo trộn,
  sau đó gán cho từng câu TN. Phép hoán vị được chỉnh để đáp án đúng rơi vào vị trí đích
  (xem `_mix_section`). Kết quả: 12 câu thì mỗi chữ cái có đúng 3 câu.
* `MixOptions` bật/tắt từng thao tác:
  * trộn câu;
  * trộn phương án trắc nghiệm;
  * trộn ý câu Đúng/Sai;
  * cân bằng đáp án;
  * giữ mã đề đầu là đề gốc.
* `matrix_from_questions` dựng ma trận từ một đề có sẵn bằng cách đếm số câu theo
  (loại câu, ID ở mức bài/dạng/chương, mức độ). Dùng để «ra đề tương đương đề năm ngoái».
* `overlap_report` tính tỉ lệ câu trùng giữa từng cặp mã đề. `answer_distribution` đếm số câu A/B/C/D.

Có hai chế độ tạo mã đề:

* `same_questions=True`: mọi mã đề dùng cùng một bộ câu và chỉ hoán vị. Đây là kiểu đề kiểm tra tập trung.
* `same_questions=False`: mỗi mã đề rút một bộ câu khác.

## 7b. Rà soát đáp án và lời giải (`review.py`)

Mỗi câu được kiểm tra và trả về danh sách `Issue(level, code, msg)`, với `level` là **Lỗi** hoặc **Cảnh báo**.

| Loại câu | Lỗi | Cảnh báo |
|---|---|---|
| Trắc nghiệm | không đủ 4 phương án; không đúng 1 `\True`; phương án rỗng hoặc trùng nhau (so sau khi chuẩn hoá: `\dfrac{1}{2}` ≡ `\frac12`); lời giải ghi «Chọn C» mà `\True` ở B | cuối lời giải có phương án sai mà không thấy đáp án đúng |
| Đúng/Sai | không đủ 4 ý; mục `\itemch` thứ k mở đầu «Đúng»/«Sai» ngược với đánh dấu `\True` của ý k | số mục `\itemch` khác số ý; có ý không ghi rõ Đúng/Sai |
| Đúng/Sai (thêm) | | cả 4 ý cùng Đúng hoặc cùng Sai (đề dễ đoán) |
| Trả lời ngắn | không có đáp án; đáp án không phải số (phiếu thi chỉ tô được chữ số, dấu `-` và `,`); **dài quá 4 kí tự**; đáp án dạng phân số `\frac`/`a/b`; có chữ hoặc đơn vị (theo CV 1239) | giá trị đáp án không có trong lời giải (thiếu bước kết luận hoặc sai đáp án) |
| Mọi câu | LaTeX hỏng: ngoặc `{}` lệch, số dấu `$` lẻ, `\begin`/`\end` không khớp, `\left`/`\right` lệch; `\includegraphics` trỏ tới **file ảnh không tồn tại** (khi rà soát file) | thiếu ID, thiếu lời giải |

Một số kĩ thuật dùng trong `review.py`:

* So khớp số «nguyên cụm» (`has_token`) để `-1` không bị khớp vào `-12`.
* Chuẩn hoá biểu thức (`norm_math`) trước khi so khớp.
* `remove_questions_text` xoá đúng khối câu khỏi file và giữ nguyên phần còn lại.
  Khi rà soát file, kết quả luôn được lưu thành **file mới**; file gốc không bị ghi đè.

**Tự sửa** (`fix_question`, `add_conclusion`). Trước tiên giáo viên chọn tin vào bên nào khi đáp án lệch lời giải:

| Tình huống | Tin lời giải | Tin đáp án |
|---|---|---|
| TN: lời giải «Chọn C», `\True` ở B (hoặc có 2 `\True`) | dời `\True` sang C | đổi chữ trong lời giải thành «Chọn B» (chỉ khi có đúng 1 `\True`) |
| Đúng/Sai: mục `\itemch` ghi «Đúng» mà ý không có `\True` | sửa `\True` theo lời giải | đổi chữ «Đúng/Sai» trong lời giải |

Các sửa khác, áp dụng như nhau với cả hai lựa chọn:

* Trả lời ngắn dùng dấu chấm thập phân, ví dụ `0.5`, được đổi thành `0{,}5`.
* Lời giải thiếu kết luận được thêm câu «Chọn đáp án \textbf{X}» (trắc nghiệm) hoặc «Vậy đáp án là …» (trả lời ngắn).

Nút **⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI** làm hai bước:

1. Sửa mọi câu sửa được.
2. Rà soát lại; câu nào vẫn còn **Lỗi** thì bị bỏ (xoá khỏi kho, hoặc bỏ khỏi file mới).

Những câu không thể tự sửa: phương án trùng nhau; hai `\True` mà lời giải không ghi «Chọn X»;
đáp án trả lời ngắn không phải số; LaTeX hỏng.

Trong file, câu đã sửa được ghi lại bằng `Question.to_latex()`; phần còn lại của file giữ nguyên.

Khi **trộn phương án**, `shuffle_choices` cũng đổi chữ trong «Chọn X» theo hoán vị.
Nhờ vậy lời giải của mọi mã đề vẫn khớp đáp án.

Dòng lệnh: `python -m nganhangde review de.tex --fix theo-loi-giai --add-conclusion --remove-errors -o de_sach.tex`.

Rà soát chỉ phát hiện **mâu thuẫn hình thức**, ví dụ lời giải và đáp án lệch nhau hay đáp án sai dạng.
Nó **không tự giải lại bài**. Một câu cả đáp án lẫn lời giải cùng sai một cách nhất quán thì không phát hiện được,
nên giáo viên vẫn cần duyệt các câu quan trọng.

Cách dùng:

* **Giao diện:** mở tab **✅ Rà soát**, chọn nguồn là kho hoặc một file `.tex`, bấm *RÀ SOÁT*.
  Bấm *Đánh dấu mọi câu Lỗi* rồi *Xoá các câu đã đánh dấu*. Có thể nhấp đúp để sửa câu, hoặc xuất báo cáo CSV.
* **Dòng lệnh:** `python -m nganhangde review de.tex --remove-errors -o de_sach.tex` cho file;
  `python -m nganhangde review --remove-errors` để xoá câu lỗi trong kho.

## 7c. Map ID và gán ID (`idmap.py`, `idsuggest.py`)

**Map ID** là file `Map_ID.tex` phân cấp bằng gạch ngang. Số gạch cho biết cấp:

| Số gạch | Cấp |
|---|---|
| 1 | lớp |
| 4 | môn |
| 7 | chương |
| 10 | bài |
| 13 | dạng |

Dòng không có gạch, ví dụ `[N] Nhận biết`, là tên mức độ.

`parse_dash_text` duyệt từng dòng, giữ một «đường dẫn hiện tại» `[lớp, môn, chương, bài, dạng]`, rồi sinh khoá bỏ kí tự mức độ:
`0`, `0D`, `0D1`, `0D11`, `0D11-1`. Với mã khai báo trùng thì giữ mục đầu; `dash_duplicates` liệt kê các mã trùng để cảnh báo.
`to_dash_text` xuất ngược lại đúng định dạng này.

**Gợi ý ID** lấy từ hai nguồn:

1. `Suggester` – **câu giống trong kho**:
   * tách từ, kể cả cụm 2 từ như `tập_nghiệm` hay `tiêu_cự`, và lệnh LaTeX;
   * đánh trọng số TF-IDF, đo độ giống cosine qua chỉ mục ngược để chạy nhanh với kho lớn;
   * lấy ID của các câu giống nhất. Kho càng nhiều câu có ID thì gợi ý càng đúng.
2. `MapSuggester` – **tên trong Map ID**:
   * mỗi dạng là một «tài liệu» ghép tên chương, tên bài và tên dạng (tên dạng có trọng số cao nhất);
   * so với chữ trong đề bài, phương án và đầu lời giải;
   * dùng được ngay cả khi kho trống; có thể giới hạn phạm vi theo lớp.

Hai nguồn được gộp lại bằng `combine`. Trước khi so, cách bỏ dấu cũ/mới được chuẩn hoá (`toạ` ≡ `tọa`),
và vài từ đồng nghĩa được quy về một (`Niu-tơn` ≡ `Newton`). Chữ cái đơn lẻ trong công thức bị bỏ qua để tránh khớp nhầm.

**Gán ID:** `Question.set_id` đổi ID và sửa luôn nhãn `%[...]` trên dòng `\begin{ex}` của khối gốc.
Nhờ vậy khi lưu file, chỉ dòng đó thay đổi.

Hộp thoại **Gán ID** (`AssignIdDialog`) có:

* bảng câu với cột «ID mới» sửa được trực tiếp;
* nút gợi ý, kèm ngưỡng độ giống;
* bộ chọn `IdPicker`: các ô Lớp → Môn → Chương → Bài → Dạng → Mức độ nối tầng theo Map ID.
  Ô nào để «giữ nguyên» thì lấy phần đó từ ID cũ, nên chỉ chọn Mức độ là đổi riêng mức độ.

Dòng lệnh:

```bash
python -m nganhangde idmap --load Map_ID.tex
python -m nganhangde suggest-id de.tex --scope 0 --auto 0.45 -o de_ganID.tex
```

**Lưu ý:** gợi ý chỉ để tham khảo. Thử trên đề mẫu lớp 10, phần lớn câu được gợi ý đúng chương,
nhưng vẫn có câu gợi ý đầu tiên bị lệch (ví dụ «viết phương trình đường tròn» bị gợi ý «đường thẳng»).
Vì vậy phải duyệt lại trước khi lưu.

## 8. Bước 6: xuất đề (`exporter.py`)

* File mẫu `templates/de_thi.tex` có các chỗ trống: `<<TEN_DE>>`, `<<MA_DE>>`, `<<NOI_DUNG>>`, `<<MODE>>`, …
  Phần mềm điền nội dung vào các chỗ đó.
  **Thầy/cô nên thay bằng file mẫu của trường**, tức file có sẵn `\cautn`, `\indapan` và gói `ex_test`
  bản đang dùng. Trong dòng lệnh dùng `--template`, hoặc khai báo `"template"` trong file ma trận.
* Mỗi mã đề sinh ra hai file:
  * `de_<mã>.tex`: chỉ có đề, không có lời giải;
  * `loigiai_<mã>.tex`: có lời giải và bảng đáp án.
* Đáp án được ghi ra hai file CSV, mở được bằng Excel:
  * `dap_an.csv`: mỗi câu một dòng;
  * `dap_an_bang.csv`: mỗi mã đề một dòng, tiện dán vào phần mềm chấm thi.
  Đáp án trả lời ngắn được ghi dạng số thường, ví dụ `0,92`.

## 8b. Tuỳ chọn trộn đề, chuẩn THPT 2026 và đáp án cho TNMaker

**Cấu trúc chuẩn** được khai báo trong `generator.THPT_2026`: 12 – 4 – 6 câu, 90 phút, 24 mã đề.
`check_structure(rules)` so ma trận với cấu trúc này. `make_codes(n, start, digits, randomize)` sinh mã đề,
ví dụ `make_codes(24, 101, 4)` → `0101 … 0124`.

**`ExportOptions`** (trong `exporter.py`) điều khiển cách xuất:

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `renumber` | Chèn `\setcounter{ex}{0}` đầu mỗi phần, để mỗi phần đánh lại từ Câu 1 (bộ đếm `ex` của `ex_test`) |
| `official_titles` | Tiêu đề và lời dẫn từng phần theo mẫu đề thi, số câu điền tự động |
| `scoring` | In thang điểm (`SCORING`) vào file lời giải |
| `answers_xlsx`, `tnmaker_layout`, `ds_style`, `ds_symbols`, `kq_decimal` | Cấu hình file `dap_an_TNMaker.xlsx` |

**`tnmaker.py`** ghi file Excel bằng `openpyxl`:

* Mọi ô được để dạng chữ, để giữ nguyên `0101`, `0,92`, `-4`.
* Sheet *Đáp án* có hai bố cục:
  * dọc: mỗi dòng một câu (`I.1 … II.1 … III.6`), mỗi cột một mã đề;
  * ngang: mỗi dòng một mã đề.
* Phần II gộp thành một ô `ĐSĐS`, hoặc tách 4 ô `II.1a … II.1d`.
* Sheet *Thông tin* ghi cấu trúc và thang điểm. Sheet *Mã đề – câu gốc* ghi ID và mã câu trong kho để đối chiếu.

Mỗi phần mềm chấm (TNMaker, …) có mẫu đáp án riêng, và mẫu này có thể đổi giữa các phiên bản.
Vì vậy bố cục được để **cấu hình được**, không cố định một kiểu.
Nếu mẫu của TNMaker khác, có thể thêm bố cục mới trong `write_answer_xlsx`.

Trong giao diện, mục **«Tuỳ chọn trộn đề»** (`ExamOptionsBox`) có 4 thẻ: Mã đề · Trộn · Trình bày · Phiếu chấm TNMaker.
Nút **⭐ Áp dụng chuẩn đề thi tốt nghiệp THPT 2026** đặt sẵn tất cả các tuỳ chọn trên.
Dòng lệnh: `python -m nganhangde make ma_tran.json --chuan-2026`, hoặc `shuffle de.tex --chuan-2026`.

## 8b-2. Giai đoạn 2: câu chùm, giới hạn đáp án liền nhau, thang điểm, phiếu chấm, ma trận CV 7991

**Trộn theo khối** (`generator._mix_section`). Câu gắn `%[chum:TÊN]` gom thành một khối (`_blocks`); thứ tự
các khối được xáo, câu trong khối giữ nguyên. Sau khi đặt đáp án theo danh sách đích A,B,C,D đã xáo (cân bằng),
vòng lặp sửa **dãy cùng chữ dài hơn `max_run`**: chọn một câu trong dãy và một câu khác có chữ khác,
**đổi chéo vị trí đích** của hai câu rồi trộn lại phương án. Số lượng mỗi chữ không đổi nên vẫn cân bằng.

**Thang điểm** (`scoring.Scoring`): `tn`, `kq`, `ds` (4 số), `tl` (từng câu). `ExportOptions.diem` là dict
(nhận cả `"0,25"`), `scoring_obj()` dựng đối tượng. `scoring_tex`, bài online (biến JS `S`), Moodle và sheet
«Thông tin» đều dùng chung.

**Phiếu chấm** (`omr.py`):
* `check_capacity` so với phiếu mẫu 2025 (40 · 8 · 6) và kiểm tra đáp án trả lời ngắn ≤ 4 kí tự `0-9 - ,`;
* `fill_template` mở file mẫu .xlsx của phần mềm chấm, tìm dòng có ô «Mã đề» (mẫu ngang) hoặc cột có ô «Câu»
  (mẫu dọc), đọc nhãn câu bằng `parse_label` (`I.1`, `II.2b`, `Câu 5`, `7`) rồi điền. Nhãn không có số La Mã
  đánh số liên tục TN → ĐS → TLN. Không đoán định dạng của từng hãng – dùng chính file mẫu của họ;
* `qr_tex` sinh `\qrcode{0101|I:ABCD…|II:1010,…|III:0,5;…}` (gói `qrcode` có sẵn trong TeX Live/MiKTeX;
  `export_versions` tự chèn `\usepackage{qrcode}`).

**Ma trận CV 7991** (`matrix.py`): `build_table` gom dòng ma trận theo chương (3 kí tự đầu của mẫu ID) và
(dạng câu, cấp độ). Cấp độ lấy từ cột Mức độ hoặc kí tự thứ 4 của ID; «C» tính vào Vận dụng. `export_xlsx` vẽ
bảng có ô gộp, tổng câu/điểm/tỉ lệ, kèm sheet «Dòng ma trận» để `import_xlsx` nạp lại. `export_docx` đi qua
HTML → pandoc.

## 8c. Đề online, Moodle, Word (`htmlconv.py`, `online.py`, `wordconv.py`)

### LaTeX → HTML (`htmlconv.py`)

1. Công thức (`$..$`, `$$..$$`, `\(..\)`, `\[..\]`, môi trường toán) được **thay tạm bằng kí hiệu giữ chỗ**.
   Nhờ vậy các lệnh như `\textbf{Công đoạn $1$:}` có công thức bên trong vẫn xử lí đúng.
2. Phần chữ được đổi sang HTML:
   * `\textbf` → `<b>`;
   * `itemize`/`enumerate`/`itemchoice` → `<ul>`/`<ol>`; danh sách lồng nhau được tìm `\end` khớp đúng cấp;
   * `\\` → `<br>`;
   * TikZ hay bảng tabular → ô «[Hình vẽ – xem bản in]».
3. Trả công thức về chỗ cũ. Công thức được escape `<` `>` `&` để MathJax đọc đúng.

### Bài làm online (`online.version_html`)

Mỗi mã đề là một file HTML tự chứa:

* CSS dành cho điện thoại; công thức dài cuộn ngang trong khung riêng, không làm rộng cả trang.
* MathJax 3 tải từ cdnjs, kèm các macro `\heva`, `\hoac`.
* Đáp án mã hoá base64 nhúng trong file.
* JavaScript chấm điểm theo thang điểm thi tốt nghiệp, chuẩn hoá dấu thập phân (`0.5` ≡ `0,5`).
* Đồng hồ đếm ngược; hết giờ thì tự nộp.

Đã kiểm thử bằng Chromium giả lập iPhone 13: điểm tự chấm khớp với tính tay.

### Moodle XML (`online.moodle_xml`)

| Loại câu | Kiểu câu hỏi Moodle |
|---|---|
| Trắc nghiệm | `multichoice` |
| Đúng/Sai | `cloze` với 4 ô `{1:MULTICHOICE:=Đúng~Sai}` |
| Trả lời ngắn | `shortanswer` (nhận cả dấu phẩy và dấu chấm) |
| Tự luận | `essay` |

Công thức được đổi sang dạng `\( \)` mà bộ lọc MathJax của Moodle dùng.

### Word ↔ LaTeX (`wordconv.py`)

Phần này dùng **pandoc**.

* **LaTeX → Word:** câu hỏi được viết lại thành LaTeX chuẩn (bỏ macro `ex_test`, thêm định nghĩa `\heva`, `\hoac`),
  rồi chạy `pandoc -t docx`. Công thức thành **OMML**, tức công thức Word gốc.
* **Word → LaTeX:** chạy `pandoc -f docx -t latex`, rồi nhận dạng theo từng dòng:
  * `Câu n` bắt đầu câu mới;
  * `A.`…`D.` (một hay nhiều phương án trên một dòng) là phương án;
  * `a)`…`d)` là ý;
  * `Đáp án:` là đáp án trả lời ngắn;
  * `Lời giải:` là lời giải;
  * đáp án là chữ cái được **gạch chân**;
  * danh sách đánh số tự động của Word được làm phẳng trước khi nhận dạng (`_flatten_lists`).

  Kết quả nên chạy qua **Rà soát** để bắt những câu chưa nhận ra đáp án.
  Đã kiểm thử: xuất kho mẫu ra Word rồi đọc lại khớp 22/22 câu, cả loại câu lẫn đáp án.

## 8d. Sinh câu hỏi số (`mathgen.py`)

**Câu mẫu** là một khối `ex` bình thường, thêm các dòng khai báo `%@`:

| Khai báo | Ý nghĩa |
|---|---|
| `%@ a = 1..9` | số nguyên ngẫu nhiên |
| `%@ b = -5..5 khac 0` | loại trừ giá trị |
| `%@ c = [2,3,5]` | chọn trong danh sách |
| `%@ d = 0.5..3 buoc 0.5` | số thực theo bước |
| `%@ D = b*b-4*a*c` | biểu thức tính từ biến đã có |
| `%@ dk: D > 0` | điều kiện |

**Cách sinh một biến thể:**

1. `parse_template` tách phần khai báo khỏi thân câu.
2. `instantiate` rút giá trị cho từng biến theo thứ tự khai báo. Nếu điều kiện sai thì rút lại, tối đa 500 lần.
3. `substitute` thay mỗi `@{…}` bằng giá trị đã định dạng.
   * Biểu thức được tính bằng `eval` với **danh sách hàm cho phép** (không có hàm dựng sẵn, chặn `__`, `import`).
   * Các hàm: `frac` (phân số tối giản), `dec` (thập phân dấu phẩy), `term` (hạng tử có dấu: «+ x», «- 3x», 0 thì bỏ),
     `coef`, `sq` (căn rút gọn), `C`, `A`, `fact`…
4. `generate` kiểm tra mỗi biến thể bằng `review_question` và bỏ câu trùng (`fingerprint`).

Kiểm thử thay ngược nghiệm vào tam thức để chắc đáp án đúng về mặt toán học.

## 8e. Vẽ hình (`drawgen.py`)

**Hàm số** được nhập theo cách viết thông dụng: `x^3-3x+1`, `(2x+1)/(x-1)`.
`to_python` thêm dấu nhân ngầm, `make_func` dịch biểu thức an toàn, chỉ cho phép các hàm `sqrt`, `sin`, `exp`, `ln`…

**Bảng biến thiên** (`variation_table`) tính hoàn toàn bằng số, gồm các bước:

1. Tìm điểm không xác định có giới hạn vô cực (`_poles`): mẫu bằng 0 đúng tại mắt lưới, hoặc đổi dấu kèm giá trị bùng nổ.
2. Tìm nghiệm của đạo hàm số (đạo hàm sai phân trung tâm), bằng cách quét lưới rồi chia đôi.
3. Làm tròn nghiệm về phân số đơn giản (`_snap`).
4. Tính giá trị tại các mốc và giới hạn ở ±∞; xác định chiều biến thiên trên từng khoảng.

Kết quả là các hàng `\tkzTabInit` / `\tkzTabLine` / `\tkzTabVar`. Tiệm cận đứng dùng `d` và `-D+`.
Số được hiển thị đẹp (`nice`): số nguyên, phân số, $a\sqrt{b}$.

**Đồ thị** (`graph_tikz`): toạ độ điểm được tính sẵn (`plot coordinates`) nên không phụ thuộc pgfmath.
Đường cong được tách đoạn ở chỗ hàm không xác định hoặc nhảy vọt, ví dụ $y=1/x$ ra 2 nhánh.

**Biểu đồ cột và biểu đồ quạt:** vẽ bằng TikZ thuần.

Giao diện có `PlotView` (QPainter) để **xem trước không cần LaTeX**.

**Đã biên dịch thử bằng pdflatex** (TikZ + tkz-tab), không có lỗi:

* bảng biến thiên của $x^3-3x+1$, $\frac{2x+1}{x-1}$ (có vạch kép tiệm cận), $\frac{x^2+x+1}{x+1}$, $x^4-2x^2$;
* đồ thị bậc ba và đồ thị $y=1/x$;
* biểu đồ cột và biểu đồ quạt.

## 8f. Biên dịch PDF (`pdfbuild.py`)

**Tìm trình biên dịch** (`find_engine`) theo thứ tự:

1. đường dẫn người dùng chỉ định;
2. `PATH`;
3. các thư mục cài hay gặp: MiKTeX trong `Program Files` / `LOCALAPPDATA`, TeX Live `C:\texlive\20xx\bin\…`.

Thứ tự ưu tiên là pdflatex → xelatex → lualatex, đổi được.

**Biên dịch** (`compile_tex`):

* Chạy `-interaction=nonstopmode -halt-on-error`, mặc định 2 lượt (ex_test cần lượt sau để đọc file đáp án),
  có giới hạn thời gian.
* Trên Windows chạy kèm `CREATE_NO_WINDOW` để không bật cửa sổ đen.
* Đọc file `.log`: mỗi dòng `! …` kèm `l.<số>` được dịch thành câu dễ hiểu (bảng `FRIENDLY`).
* Biên dịch thành công thì xoá file phụ; lỗi thì giữ `.log` để xem.

**Gói ex_test rút gọn** (`templates/nhd_extest.sty`):

* Dùng khi `kpsewhich ex_test.sty` không thấy gói.
* Được chép tạm vào thư mục biên dịch dưới tên `ex_test.sty`, xong thì xoá.
* Định nghĩa `ex`, `\choice` (đo độ rộng phương án dài nhất để chọn 4, 2 hay 1 cột), `\choiceTF`, `\shortans`, `\loigiai`,
  `\True` (tô đỏ ở bản lời giải), `itemchoice`, và bỏ qua `\Opensolutionfile`…

**File mẫu đề** dùng `iftex`:

* pdflatex dùng gói `vietnam`;
* xelatex/lualatex dùng `fontspec`, phông Times New Roman → TeX Gyre Termes → Liberation Serif → Latin Modern.

**Giao diện:**

* `BuildWorker` (QThread) biên dịch ở luồng nền, có `QProgressDialog` và nút Huỷ;
* `PdfResultDialog` hiện kết quả từng file;
* `PdfSettingsDialog` để cài đặt;
* xem trước câu (`preview_questions`) dựng tài liệu tạm từ file mẫu.

**Đã kiểm thử bằng pdflatex và xelatex:** đề và lời giải xuất từ kho mẫu biên dịch thành công.
File cố ý lỗi được báo đúng «Dòng 4: … lệnh không tồn tại».

## 8g. Gán ID bằng Gemini (`aiid.py`)

**`GeminiClient`** gọi REST API `models/{model}:generateContent` bằng `urllib`:

* khoá API gửi trong header `x-goog-api-key`;
* yêu cầu Gemini trả JSON (`responseMimeType: application/json`), `temperature` thấp để kết quả ổn định;
* lỗi 429, 500, 503 thì thử lại; lỗi 401/403/404… được dịch sang câu dễ hiểu.

`list_models()` lấy danh sách mô hình hỗ trợ `generateContent`, để người dùng chọn mà không phải gõ tên mô hình.

**Lời nhắc** (`build_prompt`) gồm:

* thang mức độ N/H/V/C kèm mô tả;
* bảng mã dạng trong phạm vi (`map_catalog`: `0D71-2 | Lớp 10 › … › Dạng …`);
* nhóm câu hỏi: đề bài, phương án, tóm tắt lời giải;
* yêu cầu trả JSON `{"ket_qua": [{"cau", "ma", "muc_do", "tin_cay", "ly_do"}]}`.

**`classify`** gửi theo nhóm (mặc định 10 câu mỗi lần), rồi với từng kết quả:

* **chỉ nhận mã có trong Map ID**, chống việc AI tự nghĩ ra mã;
* ghép mức độ vào để thành ID đầy đủ, ví dụ `0D71-2` + `H` → `0D7H1-2`;
* không dùng mức độ của AI (hoặc AI không trả) thì giữ mức độ cũ, hoặc dùng mức mặc định.

Giao diện chạy phần này ở `AiWorker` (QThread), có nút Dừng. Worker chỉ dùng dữ liệu đã chuẩn bị sẵn,
**không truy cập SQLite từ luồng nền**.

**Kiểm thử** dùng `transport` giả lập, trả về đúng cấu trúc phản hồi của Google
(`candidates[0].content.parts[0].text`), có cả JSON nằm trong khối \`\`\`json và mã bịa.
Phần này **chưa được chạy với Gemini thật**, vì máy phát triển không gọi được API của Google.

## 8h. Tự cập nhật và TeXstudio (`updater.py`, `editor.py`)

**Tự cập nhật:**

1. `latest_release()` đọc `api.github.com/repos/…/releases/latest`, lấy số phiên bản, ghi chú,
   link `NganHangDe.exe` và `digest` (`sha256:…`) mà GitHub tự tính cho mỗi file đính kèm.
2. `download()` tải theo từng khối, báo tiến trình, có thể huỷ, kiểm tra dung lượng và SHA-256.
   Mã không khớp thì xoá file và báo lỗi.
3. Windows **không cho ghi đè file exe đang chạy**. Vì vậy `apply_update()` tạo một file `.bat`
   (`update_script`), chạy ẩn và tách khỏi phần mềm. Script này:
   * chờ tiến trình cũ thoát (`tasklist /FI "PID eq …"`, tối đa 60 giây);
   * sao lưu bản cũ thành `NganHangDe_cu.exe`;
   * chép bản mới vào chỗ cũ;
   * mở lại phần mềm, rồi tự xoá.
4. Phần mềm gọi script rồi thoát ngay.

Đã thử đọc bản phát hành thật và tải thật exe 43 MB (SHA-256 khớp).
**Bước chạy `.bat` chỉ kiểm thử nội dung script**, chưa chạy trên Windows thật.

Lúc khởi động, `UpdateWorker` (QThread) kiểm tra ngầm sau 3 giây, chỉ với bản exe.
Bản mới bị người dùng «bỏ qua» thì không hỏi lại.

**TeXstudio:** `find_texstudio()` tìm trong `PATH`, `Program Files`, `LOCALAPPDATA\Programs`.
`open_in_texstudio(path, line)` dùng tham số `--line` để nhảy tới dòng lỗi lấy từ `pdfbuild`.

## 9. Bước 7: giao diện

Giao diện Qt chia thành gói `ui/` (mỗi tab, mỗi hộp thoại một file). `MainWindow` ghép từ `QMainWindow`
và mixin `BankActionsMixin`. Kiểm thử `tests/test_gui.py` chạy toàn bộ tab/hộp thoại ở chế độ `offscreen`
để phát hiện lỗi import khi tái cấu trúc.

**Dòng lệnh** (`cli.py`):

```bash
python -m nganhangde import 0-1-De-chuan-hoa-1.tex     # nạp vào nganhang.db
python -m nganhangde check  de_moi.tex                 # soát lỗi + báo câu trùng trước khi nạp
python -m nganhangde list --id "0H9*" --type TN        # lọc
python -m nganhangde stats                             # thống kê lớp/chương/loại/mức độ
python -m nganhangde make ma_tran_mau.json -n 4 -o de_xuat --seed 2026
python -m nganhangde export --id "0D8*" -o chuong8.tex  # trích câu ra file .tex
python -m nganhangde shuffle de.tex --codes 132,209,357,485 -o de_tron   # trộn thẳng 1 file đề
python -m nganhangde idmap --load idmap_mau_lop10.txt  # nạp giải nghĩa ID
python -m nganhangde backup saoluu.db                  # sao lưu kho
python -m nganhangde gui                               # mở giao diện cửa sổ
```

**Giao diện cửa sổ** (`gui_qt.py`, viết bằng PySide6). Cửa sổ chính có menu, thanh công cụ và **4 tab**
(ảnh chụp trong thư mục `docs/`):

| Tab | Nội dung |
|---|---|
| 📚 **Ngân hàng câu hỏi** | Bên trái là **cây chương**, hiện tên chương lấy từ bảng giải nghĩa ID, và **bộ lọc** (loại câu, mức độ, mẫu ID, từ khoá). Ở giữa là bảng câu hỏi. Bên dưới có ba tab: *Thông tin* (giải nghĩa đủ chương → bài → dạng), *Mã LaTeX*, và *Câu tương tự* (các câu cùng dạng, cùng mức độ; nhấp đúp để sửa) |
| 📝 **Tạo đề** | Bên trái: thông tin đề và **tuỳ chọn trộn** (trộn câu, trộn A–D, trộn ý Đúng/Sai, cân bằng đáp án, giữ đề gốc). Bên phải: ma trận đề có cột «Kho có» và nút **Ma trận từ đề có sẵn…**. Tạo xong sẽ hiện bảng phân bố đáp án A/B/C/D và tỉ lệ trùng giữa các mã đề |
| 🛠 **Công cụ** | Làm việc trực tiếp trên file `.tex`: soát lỗi, tìm câu trùng, thống kê theo ID, lọc câu theo ID, đổi ID hàng loạt, **trộn đề trực tiếp từ file**, lấy bảng đáp án, thêm nguồn cho mọi câu, gộp và sắp xếp theo ID, xoá lời giải, nạp vào kho |
| ✅ **Rà soát** | Kiểm tra đáp án, lời giải và LaTeX của cả kho hoặc một file. Mỗi câu được xếp mức Lỗi (đỏ) hoặc Cảnh báo (cam). Cột «Tự sửa được» cho biết trước sẽ sửa gì. Có các nút: *Sửa các câu đã đánh dấu*, **⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI**, xoá câu đã đánh dấu (với file thì lưu thành file mới), nhấp đúp để sửa tay, xuất báo cáo CSV (xem mục 7b) |
| 📊 **Thống kê** | Các ô tổng số câu theo loại, và bảng số câu theo chương × mức độ |

Các công cụ trong tab Công cụ được viết ở `tools.py` (có kiểm thử), không phụ thuộc giao diện.

* **Thêm/Sửa câu:** khung soạn LaTeX có tô màu và nút chèn mẫu cho 4 loại câu.
  Phần mềm kiểm tra ngay khi gõ và hiện loại câu, ID, đáp án, lỗi.
* **Tạo đề:**
  * lập ma trận theo từng dòng (loại, mẫu ID, mức độ, số câu); cột «Kho có» cho biết kho còn đủ câu không;
  * lưu và mở ma trận bằng file `.json`;
  * đặt danh sách mã đề, seed, file mẫu `.tex` riêng;
  * biên dịch PDF nếu máy có `xelatex`;
  * mở thư mục kết quả sau khi tạo xong.
* Phần mềm nhớ kho đang dùng và các thông số tạo đề lần trước (`QSettings`).
* Menu **Tệp** có thêm: *Sao lưu kho*, *Gộp kho khác vào*, *Tách câu đã chọn ra kho mới*.
  Menu **Công cụ** có thêm: *Giải nghĩa ID (Map ID)*, nhập và xuất bằng file `.txt`.
  Xem file mẫu `idmap_mau_lop10.txt`.

Kĩ thuật chính trong `gui_qt.py`:

* `QSyntaxHighlighter`: tô màu lệnh `\...`, công thức `$...$`, comment, `\True` và ID.
* `QTableWidget` có `setSortingEnabled(True)`. Mã `db_id` của câu được cất trong `Qt.UserRole`
  để lấy lại khi người dùng chọn dòng.
* Cây chương được dựng từ `Bank.stats()`. Mỗi nút giữ một dict bộ lọc (`{"lop": "0", "chuong": "9"}`),
  khi bấm vào nút thì truyền dict đó cho `Bank.search()`.
* Giao diện chỉ gọi các hàm của phần lõi, không chứa logic xử lí đề.

## 10. Cài đặt, chạy và đóng gói file .exe

**Chạy từ mã nguồn** (cần Python 3.10+):

```bash
pip install -r requirements.txt     # cài PySide6
python -m nganhangde gui            # mở giao diện
pip install pytest && python -m pytest -q   # chạy kiểm thử
```

**Cách 1: tự đóng gói trên máy Windows.**

1. Cài Python 3.12 từ python.org. Khi cài, tích ô **Add python.exe to PATH**.
2. Nhấp đúp file **`build_exe.bat`**. Kịch bản sẽ:
   * tạo môi trường ảo `.venv`;
   * cài PySide6 và PyInstaller;
   * đóng gói chương trình.
3. Sau khoảng 2–5 phút sẽ có file **`dist\NganHangDe.exe`**, dung lượng khoảng 50–70 MB.
   File này chép sang máy khác dùng được ngay, không cần cài Python.

Lệnh đóng gói bên trong `build_exe.bat`:

```bat
pyinstaller --noconfirm --clean --onefile --windowed --name NganHangDe ^
    --icon nganhangde\assets\app.ico ^
    --add-data "nganhangde/templates:nganhangde/templates" ^
    --add-data "nganhangde/assets:nganhangde/assets" ^
    --exclude-module tkinter run_gui.py
```

Ý nghĩa các tuỳ chọn:

* `--onefile`: gộp mọi thứ vào 1 file exe.
* `--windowed`: không hiện cửa sổ đen (console).
* `--add-data`: đưa file mẫu đề và biểu tượng vào exe. Lúc chạy, exe giải nén chúng vào thư mục tạm.
  Vì vậy `exporter.py` tìm file mẫu theo đường dẫn tính từ `__file__`.

**Cách 2: để GitHub đóng gói hộ, không cần cài gì.**

1. Đưa code lên GitHub.
2. Vào tab **Actions**, chọn **Build exe**, bấm **Run workflow**.
3. Chờ khoảng 5 phút, rồi tải `NganHangDe-windows` ở mục **Artifacts**.

Quy trình này chạy kiểm thử, đóng gói, rồi chạy `NganHangDe.exe --selftest` để chắc file exe hoạt động.
Nếu đẩy một tag dạng `v1.0.0`, file exe được gắn luôn vào trang **Releases**.

**Lưu ý khi dùng exe:**

* Kho mặc định `nganhang.db` nằm **cạnh file exe**. Mở kho khác bằng menu Tệp → Mở kho.
* Muốn sao lưu thì chép file `.db`.
* Windows SmartScreen có thể cảnh báo vì exe chưa được kí số. Bấm «More info» → «Run anyway».

Biên dịch đề đã xuất: `xelatex de_101.tex` (cần gói `ex_test` trong cùng thư mục hoặc trong TeX).

## 11. Đối chiếu chức năng với MyLT

MyLT viết bằng **Visual Basic .NET (WinForms)** trên .NET Framework 3.5, và dùng Office Interop để làm việc với Word/Excel.
Phần mềm này viết bằng **Python + PySide6 (Qt)**. Ngôn ngữ này chạy được cả Windows/macOS/Linux,
đóng gói thành `.exe` bằng PyInstaller, và kiểm thử tự động được.

Bảng dưới lập từ tên các thành phần giao diện trong file `MyLT.exe`. Mã nguồn MyLT không được
đọc hay sao chép; phần mềm này tự viết các chức năng tương ứng.

| Nhóm chức năng của MyLT | Phần mềm này |
|---|---|
| Ngân hàng: nhập file, lọc Lớp/Môn/Chương/Bài/Dạng/Mức độ, tìm theo ID | ✅ |
| Giải nghĩa ID (Map ID), nạp thẳng file Map_ID.tex | ✅ |
| Gán ID / đổi mức độ cho nhiều câu, gợi ý ID tự động | ✅ (gợi ý tự động là phần thêm) |
| Câu tương tự | ✅ |
| Sao lưu kho, gộp kho (Joiner), tách kho (Extract) | ✅ |
| Soát lỗi, tìm câu trùng | ✅ |
| **Rà soát đáp án – lời giải, tự sửa, bỏ câu sai** | ✅ (MyLT có kiểm tra câu lỗi; phần đối chiếu đáp án với lời giải và tự sửa là phần thêm) |
| Tạo đề theo ma trận, nhiều mã đề, danh sách mã đề | ✅ |
| Ma trận từ đề có sẵn | ✅ |
| Cân bằng tỉ lệ đáp án | ✅ |
| Không trộn câu / không trộn ý Đúng/Sai | ✅ |
| Kiểm tra tỉ lệ trùng giữa các đề | ✅ |
| Đáp án ra bảng Excel (CSV) | ✅ |
| Công cụ trên file: lọc ID, đổi ID, thêm nguồn, sắp xếp, lấy đáp án, xoá lời giải, trộn đề từ file | ✅ |
| Đổi câu trong đề trước khi trộn | ✅ (`SwapDialog`, `generator.replacement_pool`) |
| Xếp câu theo mức độ, giới hạn tỉ lệ trùng giữa các đề | ✅ (`MixOptions.sort_by_level`, `make_versions(max_overlap=…)`) |
| In ma trận đặc tả | ✅ (`exporter.matrix_spec`) |
| Lịch sử sửa câu, khôi phục câu đã xoá | ✅ (bảng `history`, `Bank.restore`) |
| Tìm & thay thế, xoá ID, xoá nguồn, lọc theo nguồn, trích TikZ, câu gần trùng | ✅ (`tools.py`, `Bank.replace_text`) |
| Kiểm tra cập nhật, **tự cập nhật** | ✅ (mục 8h – tải exe, kiểm tra SHA-256, tự thay và mở lại) |
| Mở bằng trình soạn LaTeX (TeXstudio) | ✅ (mục 8h – nhảy tới dòng lỗi) |
| Đáp án cho phần mềm chấm phiếu (TNMaker) | ✅ file Excel cấu hình được bố cục |
| Chuẩn đề tốt nghiệp (24 mã, đánh số từng phần, lời dẫn, thang điểm) | ✅ |
| In phiếu trả lời, mã QR, Azota | ⏳ chưa có (phiếu dùng mẫu của TNMaker) |
| Chuyển Word ↔ LaTeX | ✅ qua pandoc (mục 8c) |
| Đề online (HTML tự chấm), Moodle XML | ✅ (mục 8c) |
| Biên dịch PDF, xem PDF câu hỏi, báo lỗi LaTeX | ✅ (mục 8f – cần MiKTeX/TeX Live) |
| Bảng biến thiên, đồ thị hàm số, biểu đồ cột/quạt → TikZ | ✅ (mục 8e) |
| Sinh số / sinh câu từ câu mẫu | ✅ (mục 8d) |
| Dựng hình học phẳng từng bước (điểm, đường tròn, giao điểm…) | ⏳ chưa có |
| Gán ID bằng AI (Gemini) | ✅ (mục 8g – cần khoá API Gemini) |
| Sinh câu hỏi bằng AI (Gemini) | ⏳ chưa có (dùng chung `GeminiClient` được) |

## 12. Hướng phát triển thêm

| Tính năng | Gợi ý cách làm |
|---|---|
| Xem trước PDF ngay trong phần mềm | Gọi `subprocess.run(["xelatex", ...])` vào thư mục tạm, rồi mở PDF bằng `os.startfile` hoặc hiển thị qua PyMuPDF |
| Nhập đề từ Word | `pandoc de.docx -o de.tex`, rồi viết bộ chuyển `\begin{enumerate}` sang `\begin{ex}` |
| Ma trận nhập từ Excel | Đọc bằng `openpyxl`, mỗi dòng Excel ứng với một `Rule` |
| Đổi «Chọn đáp án A» trong lời giải khi trộn | Sau khi trộn, thay `\textbf{Chọn A}` theo `perm`. Hoặc để `ex_test` tự in đáp án |
| Hình TikZ hoặc ảnh đi kèm | Lưu đường dẫn ảnh vào bảng `assets` và chép ảnh theo khi xuất |
| Nhiều người cùng dùng | Đổi SQLite sang PostgreSQL và làm giao diện web (Flask hoặc FastAPI); các mô-đun `parser`, `generator`, `exporter` giữ nguyên |
| Phiếu trả lời và chấm trắc nghiệm | Dùng `dap_an.csv` làm khoá chấm |

Nguyên tắc quan trọng nhất: **phần lõi (`parser`, `db`, `generator`, `exporter`) không phụ thuộc giao diện**.
Muốn đổi sang giao diện web hay Qt thì chỉ cần viết lại lớp giao diện.
