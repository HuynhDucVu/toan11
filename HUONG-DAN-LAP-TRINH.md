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
├── review.py     # rà soát đáp án – lời giải – LaTeX, xoá câu sai
├── cli.py        # Bước 7a: dòng lệnh
├── gui_qt.py     # Bước 7b: giao diện chính (PySide6/Qt)
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
| Trả lời ngắn | không có đáp án; đáp án không phải số (phiếu thi chỉ tô được chữ số, dấu `-` và `,`) | đáp án dài quá 4 kí tự; giá trị đáp án không có trong lời giải (thiếu bước kết luận hoặc sai đáp án) |
| Mọi câu | LaTeX hỏng: ngoặc `{}` lệch, số dấu `$` lẻ, `\begin`/`\end` không khớp, `\left`/`\right` lệch | thiếu ID, thiếu lời giải |

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

## 9. Bước 7: giao diện

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
| Đổi một câu trong đề đã sinh | ⏳ chưa có (hiện phải tạo lại với seed khác) |
| Phiếu trả lời trắc nghiệm, mã QR, đề online (Azota, HTML, Moodle XML) | ⏳ chưa có |
| Chuyển Word ↔ LaTeX, xem PDF trong phần mềm | ⏳ chưa có (gợi ý ở mục 12) |
| Vẽ hình TikZ, đồ thị, bảng biến thiên, biểu đồ | ⏳ chưa có (nên làm thành mô-đun riêng) |
| Sinh câu hỏi bằng AI, sinh số ngẫu nhiên | ⏳ chưa có |

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
