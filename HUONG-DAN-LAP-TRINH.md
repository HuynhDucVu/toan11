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
> giao diện hay mã của MyLT. Nếu MyLT có chức năng nào chưa có ở đây, xem mục 8 để tự bổ sung.

Mã nguồn hoàn chỉnh nằm trong thư mục `nganhangde/` và chạy được ngay.

---

## 1. Chọn công nghệ

| Thành phần | Lựa chọn | Lí do |
|---|---|---|
| Ngôn ngữ | Python 3.10+ | Dễ học, xử lí chuỗi tốt, chạy trên Windows, macOS và Linux |
| Cơ sở dữ liệu | SQLite (`sqlite3` có sẵn) | Mỗi kho chỉ là một file `.db`, không cần cài máy chủ, dễ sao lưu và chép qua USB |
| Giao diện | Tkinter (có sẵn) | Không phải cài thêm thư viện. Muốn giao diện đẹp hơn thì đổi sang PySide6 (mục 8) |
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
├── cli.py        # Bước 7a: dòng lệnh
├── gui.py        # Bước 7b: giao diện cửa sổ
└── templates/de_thi.tex   # file mẫu đề (thay bằng mẫu của trường)
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

Có hai chế độ tạo mã đề:

* `same_questions=True`: mọi mã đề dùng cùng một bộ câu và chỉ hoán vị. Đây là kiểu đề kiểm tra tập trung.
* `same_questions=False`: mỗi mã đề rút một bộ câu khác.

## 8. Bước 6: xuất đề (`exporter.py`)

* File mẫu `templates/de_thi.tex` có các chỗ trống: `<<TEN_DE>>`, `<<MA_DE>>`, `<<NOI_DUNG>>`, `<<MODE>>`, …
  Phần mềm điền nội dung vào các chỗ đó.
  **Thầy/cô nên thay bằng file mẫu của trường**, tức file có sẵn `\cautn`, `\indapan` và gói `ex_test`
  bản đang dùng. Trong dòng lệnh dùng `--template`, hoặc khai báo `"template"` trong file ma trận.
* Mỗi mã đề sinh ra hai file:
  * `de_<mã>.tex`: chỉ có đề, không có lời giải;
  * `loigiai_<mã>.tex`: có lời giải và bảng đáp án.
* Toàn bộ đáp án của mọi mã đề được ghi vào `dap_an.csv`, mở được bằng Excel.
  File này dùng để nhập vào phần mềm chấm thi.

## 9. Bước 7: giao diện

**Dòng lệnh** (`cli.py`):

```bash
python -m nganhangde import 0-1-De-chuan-hoa-1.tex     # nạp vào nganhang.db
python -m nganhangde check  de_moi.tex                 # soát lỗi + báo câu trùng trước khi nạp
python -m nganhangde list --id "0H9*" --type TN        # lọc
python -m nganhangde stats                             # thống kê lớp/chương/loại/mức độ
python -m nganhangde make ma_tran_mau.json -n 4 -o de_xuat --seed 2026
python -m nganhangde export --id "0D8*" -o chuong8.tex  # trích câu ra file .tex
python -m nganhangde gui                               # mở giao diện cửa sổ
```

**Giao diện cửa sổ** (`gui.py`) chia làm ba vùng:

* bên trái là bộ lọc;
* ở giữa là bảng câu hỏi;
* bên dưới là khung xem mã LaTeX, kèm giải nghĩa ID và cảnh báo.

Thanh công cụ có các nút: **Nhập file .tex**, **Thêm/Sửa câu**, **Xoá**, **Xuất câu đã chọn**,
**Tạo đề (trộn đề)** và **Thống kê**.

* Nhấp đúp vào một câu để sửa trực tiếp mã LaTeX. Khi lưu, phần mềm phân tích lại câu và soát lỗi.
* Cửa sổ «Tạo đề» cho nhập ma trận theo từng dòng. Mỗi dòng gồm loại câu, mẫu ID, mức độ và số câu.

## 10. Cài đặt, chạy, đóng gói

```bash
# chạy trực tiếp (cần Python 3.10+; trên Windows Tkinter có sẵn)
python -m nganhangde gui

# kiểm thử
pip install pytest && python -m pytest -q

# đóng gói thành file .exe cho Windows
pip install pyinstaller
pyinstaller --onefile --windowed --name NganHangDe ^
    --add-data "nganhangde/templates;nganhangde/templates" run_gui.py
```

Biên dịch đề đã xuất: `xelatex de_101.tex` (cần gói `ex_test` trong cùng thư mục hoặc trong TeX).

## 11. Hướng phát triển thêm

| Tính năng | Gợi ý cách làm |
|---|---|
| Xem trước PDF ngay trong phần mềm | Gọi `subprocess.run(["xelatex", ...])` vào thư mục tạm, rồi mở PDF bằng `os.startfile` hoặc hiển thị qua PyMuPDF |
| Nhập đề từ Word | `pandoc de.docx -o de.tex`, rồi viết bộ chuyển `\begin{enumerate}` sang `\begin{ex}` |
| Ma trận nhập từ Excel | Đọc bằng `openpyxl`, mỗi dòng Excel ứng với một `Rule` |
| Đổi «Chọn đáp án A» trong lời giải khi trộn | Sau khi trộn, thay `\textbf{Chọn A}` theo `perm`. Hoặc để `ex_test` tự in đáp án |
| Hình TikZ hoặc ảnh đi kèm | Lưu đường dẫn ảnh vào bảng `assets` và chép ảnh theo khi xuất |
| Nhiều người cùng dùng | Đổi SQLite sang PostgreSQL và làm giao diện web (Flask hoặc FastAPI); các mô-đun `parser`, `generator`, `exporter` giữ nguyên |
| Giao diện đẹp hơn | Viết lại `gui.py` bằng PySide6 (Qt), phần lõi giữ nguyên |
| Phiếu trả lời và chấm trắc nghiệm | Dùng `dap_an.csv` làm khoá chấm |

Nguyên tắc quan trọng nhất: **phần lõi (`parser`, `db`, `generator`, `exporter`) không phụ thuộc giao diện**.
Muốn đổi sang giao diện web hay Qt thì chỉ cần viết lại lớp giao diện.
