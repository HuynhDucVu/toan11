## 0.17.51 – Sắp xếp thư mục theo sơ đồ chuẩn

- Moodle XML xuất vào DATA\MFORMS (cùng nhóm đề online); không còn thư mục DATA\MOODLE XML.
- Phiếu TLTN 2025 nằm trong DATA\PDF QUIZ; phần mềm vẫn tìm được phiếu ở vị trí cũ.
- Tạo sẵn các thư mục con: DATA\DE\ans, DATA\DE\build, TEMP\ans, TEMP\build, DATA\WORD2EXTEST\data, hinh, out.
- Mẫu trong TEMPLATE đổi tên thành Header.tex và nhd_extest.sty (máy đang dùng tên cũ vẫn giữ file cũ).
- Không đổi: tên kho nganhang.db và thư mục Map ID (DPS) (để không làm mất kho và Map ID đang dùng).

## 0.17.50 – Word → LaTeX: AI rà soát và xuất LaTeX chuẩn

- Sửa bản 0.17.49: kiểm tra sau chuyển (đếm câu, đáp án, lời giải) chưa được gọi trong hộp thoại; nay đã gọi và hiện trong bảng tóm tắt.
- Hộp thoại chuyển Word có tuỳ chọn mới **AI rà soát đáp án & viết lại lời giải theo mẫu LaTeX**: AI giải lại từng câu, ghi lời giải theo mẫu, báo câu AI giải ra đáp án khác (kiểm tra tay, không tự đổi đáp án), rồi ghi lại file .tex chuẩn ex_test.
- Chuyển MathType → Equation → LaTeX: dùng tuỳ chọn «Dùng Convert Equations» (cần Windows, Word và MathType) hoặc «Đọc trực tiếp».

## 0.17.49 – Word → LaTeX: tự kiểm tra sau khi chuyển

- Sau mỗi file .docx, phần mềm đếm số mốc «Câu» trong Word và so với số câu nhận được; báo câu thiếu hoặc ghép nhầm.
- Báo từng câu: trắc nghiệm không đúng 1 đáp án, câu chưa có lời giải, số dấu $ lẻ, ngoặc nhọn không cân, công thức MathType không đọc được.
- Kết quả hiện trong bảng tóm tắt, dưới tên file.

## 0.17.48 – Một cửa sổ xem PDF; biên dịch tiếng Việt không lỗi

- Xem PDF chỉ mở **một cửa sổ** trong phần mềm (mở lại thì cửa sổ cũ đóng). Không còn mở trình PDF ngoài và không còn khung xem trước riêng ở trang Vẽ hình.
- Mẫu hình (Trục số, Miền nghiệm, Đồ thị, Biểu đồ…) có gói tiếng Việt cho cả pdflatex (vietnam) lẫn xelatex/lualatex (fontspec). Lỗi «inputenc: ký tự ế chưa được hỗ trợ» đã hết.
- Mọi lần xuất đề đều chép kèm **ex_test.sty** đầy đủ cạnh file .tex, nên biên dịch đề không báo thiếu gói.

## 0.17.47 – Rà soát: AI kiểm tra đáp án, bổ sung lời giải, xoá câu trùng

- Nhóm mới **Kiểm tra nâng cao** ở tab Rà soát:
  - **AI giải & kiểm tra đáp án**: AI giải lại câu đã đánh dấu (hoặc mọi câu đang hiện). Đáp án AI khác đáp án đánh dấu ⇒ lỗi «AI: đáp án khác» để kiểm tra tay. Không tự đổi đáp án.
  - **Bổ sung lời giải thiếu bằng AI**: ghi lời giải AI viết cho câu chưa có lời giải, sau khi xác nhận.
  - **Xoá câu trùng lặp (giữ 1 câu)**: kho → quét giống hệt cả kho; file .tex → giữ câu đầu mỗi nhóm, ghi ra file mới.
  - **Đánh dấu phương án trùng**: chọn các câu có hai phương án giống nhau.

## 0.17.46 – Nhập ngân hàng nhanh hơn, báo số câu theo loại

- Tốc độ nhập: chuẩn hoá tìm kiếm (bỏ dấu tiếng Việt) được đệm và thoát sớm với chuỗi ASCII, nhanh hơn khoảng 1,7 lần khi nhập (đo trên dữ liệu thử, chưa đo trên kho MyLT thật).
- Sau mỗi lệnh nhập (Nhập ngân hàng MyLT, Nhập file .tex, Nhập file Word, Nhập câu hỏi 3 bước) hiện **ĐÃ NHẬP VÀO KHO** và **Kho hiện có**, theo các loại TN · ĐS · TLN · TL.
- Khi không đọc được kho MyLT do thiếu driver Access, thông báo hướng dẫn cài «Microsoft Access Database Engine» (miễn phí). Không cần cài Microsoft Access (Office).

## 0.17.45 – Chuyển Word → LaTeX: sửa lỗi mất nội dung

- Chỉ số trên/dưới gõ bằng định dạng Word (x², m₃) nay thành `$^{2}$`, `$_{3}$` (trước đây thành `x2`, `m3`).
- Ký hiệu chèn bằng Insert → Symbol (≤, ≥, ≠, ∞, α, π…) không còn bị mất; ký hiệu Unicode gõ thẳng cũng đổi thành lệnh LaTeX trong `$…$`.
- Dấu `%` trong văn bản (ví dụ «50%») được escape `\%`: trước đây làm LaTeX bỏ mất phần sau của dòng. `&` và `#` cũng được escape ngoài bảng.
- Thêm 4 test chuyển đổi Word (tests/test_word_conv.py).

## 0.17.44 – Thanh tab chính chia 2 hàng

- Các tab chính không còn tràn ngang: hàng trên gồm Trộn đề, Biểu diễn nghiệm, Soạn thảo, Thông tin, Cập nhật; hàng dưới gồm Câu hỏi, Ma trận, Tiện ích, Vẽ hình, Đồ thị, BBT & Xét dấu. Chọn tab ở hàng nào cũng chuyển trang; hàng không chứa trang đang mở được làm nhạt.

## 0.17.43 – HDSD: nhóm «Chuyển đổi»

- Thêm 11 mục hướng dẫn cho các chức năng chuyển đổi: tổng quan (chức năng nằm ở menu nào), Word/PDF → LaTeX, nhập Word vào kho, đề gõ thường → ex_test, Word ↔ LaTeX, nhập kho MyLT, xuất câu ra Word/Moodle/HTML, đề online (Moodle, Aiken, Quizizz, Forms, Blogger, bài làm online), phiếu trả lời, hình TikZ ra PNG/tách file, quyển chuyên đề và trình chiếu.

## 0.17.42 – Cửa sổ HDSD (hướng dẫn sử dụng)

- Thêm cửa sổ **HDSD** (Trợ giúp → HDSD, phím F1): danh mục bên trái theo nhóm chức năng, nội dung ngắn gọn bên phải, tên nút và tên tab khớp giao diện.
- Nút **HDSD** ở tab Tạo đề tự chọn và Tạo đề tương tự mở đúng mục của tab đó.

## 0.17.41 – Sửa lỗi build trên máy không có LaTeX

- Sửa lỗi làm bản build Windows không qua kiểm thử (các bản 0.17.39 và 0.17.40 không có release): khi máy chưa cài LaTeX, tạo mã hình (Trục số, Miền nghiệm, Đường tròn LG) không còn báo lỗi; bấm «Xem trước PDF» thì hiện thông báo cần cài LaTeX.

## 0.17.40 – Cỡ hình xem trước

- Khung xem trước hình (Trục số, Miền nghiệm, Đường tròn LG, Đồ thị, Biểu đồ, Bảng xét dấu, Hình khối) có ô **Cỡ hình**: Vừa khung, 50%, 100%, 150%, 200%. Chỉ đổi cách hiển thị, không đổi mã TikZ.

## 0.17.39 – Xem trước hình ngay trong trang tạo mã

- Biểu diễn nghiệm (Trục số, Miền nghiệm, Đường tròn lượng giác), Đồ thị, Biểu đồ, Bảng xét dấu, Hình khối: mỗi trang có khung **xem trước bên phải** như Bảng biến thiên. «Xem trước PDF» biên dịch rồi vẽ ngay vào khung đó (không mở cửa sổ ngoài); sau «Tạo mã» ở Trục số/Miền nghiệm/Đường tròn LG tự xem trước nếu máy có LaTeX. Bảng biến thiên cũng hiện PDF ở khung có sẵn.

## 0.17.38 – Nút nạp câu hỏi, tách Kiểm tra / Xoá lỗi, tuỳ chọn phiếu có tác dụng

- Thanh nguồn của Trộn đề có nút **🔄 Nạp câu hỏi**: nạp lại ngân hàng, hoặc đọc lại các file đã chọn (khi sửa file ngoài) vào mọi trang.
- Hộp thoại «Nhập câu hỏi»: **Kiểm tra** chỉ quét và báo (số câu sai, trùng giống hệt, lỗi hay gặp) – không xoá gì; **Xoá lỗi** xoá các câu sai sau khi xác nhận (có lịch sử, khôi phục được).
- Tuỳ chọn phiếu: **Chỉ đáp án** (không kèm phiếu trắng), **Màu vẽ** và **Nét vẽ** (cỡ ô tô) nay áp dụng cho phiếu khoá TLTN 2025. Các ô tick còn lại vẫn chỉ lưu cấu hình.

## 0.17.37 – Hộp thoại «Nhập câu hỏi vào ngân hàng» và nạp file ngay trong «Tạo đề theo file»

- «Nhập câu hỏi» mở hộp thoại như MyLT: Files (Chọn/Thêm), Không nhập câu ID5, Bỏ qua câu trùng, Kiểm tra câu trùng, Kiểm tra câu trùng sâu + Tỉ lệ (ngưỡng giống nhau dùng thật khi kiểm tra trùng sâu), các nút Hướng dẫn, Khởi tạo, Sao lưu, Kiểm tra, Ghép, Chuyển sang macOS/linux, Khôi phục, Xoá lỗi, Xuất, Nhập, Đóng. «Nhập» đi qua màn rà soát 3 bước có sẵn. «Kiểm tra» và «Xoá lỗi» cùng mở công cụ dọn kho.
- «Tạo đề theo file» có nút «Nạp vào nguồn»: nạp các file làm nguồn câu hỏi của cả tab Trộn đề (chuyển sang «Từ Files», bảng ID/tự chọn dùng luôn).

## 0.17.36 – Trộn đề theo cấu trúc MyLT 2026

- **Tạo đề tự chọn**: hàng lọc Lọc/Lớp/Môn/Chương/Bài/Dạng/Mức độ/Loại/Kiểu ID/Đã lấy; bảng STT | Nội dung câu hỏi (mã LaTeX) | Loại | ID | Chọn; thanh dưới HDSD, Sửa câu hỏi, Xoá, Chọn [N], Chọn hết, Xoá chọn, PDF, «Đã chọn: N câu», phân trang Đầu/Trước/[1]/Sau/Cuối (phân trang ngay trong SQL nên kho 150 000 câu vẫn nhanh).
- **Tạo đề theo file**: bảng STT | Tập tin | Đã có | Lấy, «Đã chọn», «Xoá chọn».
- **Tạo đề tương tự**: File đề gốc, Đề tương tự thứ N, Lưu/Đổi/Sửa, Xem PDF, Tìm theo, Tỉ lệ tương tự, Số đề tối đa, Tìm, HDSD; bảng đề gốc ↔ đề tương tự.
- **Tuỳ chọn đề**: một màn hình như MyLT (Tuỳ chọn chung, phiếu, tiêu đề, tên file đề tạo ra, lưu ma trận). Phần cũ chuyển sang tab «Nâng cao (ma trận…)». Các ô tick của «Tuỳ chọn phiếu» mới chỉ lưu cấu hình, chưa dùng khi vẽ phiếu.
- **Bảng ID**: file/ngân hàng chưa có ID (hoặc ID không đọc được) nay hiện dòng «?» và lấy ngẫu nhiên được; «Nạp lại (Map ID)» đọc lại các file trong «Map ID (DPS)»; có sẵn Map ID đi kèm khi chưa nạp.
- «Mở ngân hàng» nạp câu ngay vào các trang con.

## Tải về và chạy
Có 3 cách (chọn một):
- **NganHangDe.exe** – một file, chạy ngay, **tự cập nhật** được (khuyên dùng);
- **NganHangDe_CaiDat.exe** – bộ cài (có lối tắt ngoài màn hình, gỡ cài đặt trong Windows);
- **NganHangDe_ThuMuc.zip** – bản thư mục, mở nhanh hơn, ít bị phần mềm diệt virus nghi nhầm (giải nén rồi chạy NganHangDe.exe bên trong).

Với bản một file:
1. Tải file **NganHangDe.exe** ở mục *Assets* bên dưới.
2. Chép vào một thư mục riêng (ví dụ `D:\NganHangDe`) rồi nhấp đúp để chạy, không cần cài đặt.
3. Nếu Windows SmartScreen cảnh báo (vì file chưa ký số): bấm **More info → Run anyway**.

Kho câu hỏi `nganhang.db` nằm cạnh file exe. Cập nhật từ bản cũ: chỉ cần thay file exe, kho giữ nguyên.

## Có gì mới ở bản 0.17.35 – Nhận dạng câu Đúng/Sai viết kiểu cũ, ex_test v3.1 kèm sẵn
- **Câu Đúng/Sai viết `\TF\choice{…}{…}{…}{…}`** (cả `\MYLT[t]\TF\choice`, `\MyLTt\TF\choice`…; chữ `t` = kiểu bảng) nay được nhận là **Đúng/Sai** và đổi sang dạng chuẩn của ex_test mới (`\choiceTF` / `\choiceTFt`). Trong kho thử 153.000 câu: trước đây 0 câu, nay **3.764 câu Đúng/Sai**.
- **Nhận dạng lại kho**: lần mở đầu sau khi nâng cấp phần mềm hỏi có nhận dạng lại loại câu hỏi trong kho không (cũng có ở Công cụ → «Nhận dạng lại loại câu hỏi trong kho»). ID, nguồn, lời giải giữ nguyên.
- Kèm sẵn **ex_test v3.1 (21/10/2024)** trong `TEMPLATE\GOI LENH` (biên dịch dùng bản này, file xuất ra được chép kèm) và **Map_ID_Moi.tex** (hợp nhất 4 mức độ) trong `Map ID (DPS)` – chọn ở Giải nghĩa ID (Ctrl+M) → chọn nhanh.

## Có gì mới ở bản 0.17.34 – Xoá tạm và lịch sử để cập nhật sạch
- Tab **⬆ Cập nhật** có nút **🧹 Xoá tạm và lịch sử cập nhật**: xoá bản tải dở, file `.bat` cập nhật cũ, thư mục tạm của phần mềm, thư mục giải nén cũ `_MEI…` (bỏ qua thư mục đang dùng), thư mục `TEMP`, và lịch sử «Bỏ qua bản này» / lần kiểm tra; tuỳ chọn xoá luôn `NganHangDe_cu.exe`. Kho, cài đặt và file đã xuất không bị xoá. Phần mềm cũng tự dọn tạm trước mỗi lần tải bản mới.

## Có gì mới ở bản 0.17.33 – Tab «Tạo đề theo ID» giống MyLT hơn
- Dưới bảng: dải nút **? H A C E D O U** (hướng dẫn · chỉ hiện dòng đã lấy · chọn tất cả dòng · xoá hết số đã nhập · xuất Excel · xoá số ở dòng đang chọn · đưa vào ma trận và mở Tuỳ chọn đề · hoàn tác), nhãn **Đã chọn:** và **phân trang** Đầu / Trước / [trang] / Sau / Cuối (100 dòng một trang; số đã nhập giữ khi sang trang khác).
- Góc dưới phải tab Trộn đề có nút **Tạo đề** (tạo theo trang con đang mở) và **Thoát**.
- Ý nghĩa các nút chữ cái do tôi suy từ ảnh MyLT; nếu MyLT dùng khác, báo lại để chỉnh.

## Bản 0.17.32 – Hộp «Chọn file Map ID» mở sẵn thư mục `Map ID (DPS)`.

## Có gì mới ở bản 0.17.31 – Nhận dạng câu Đúng/Sai viết dạng môi trường
- Câu Đúng/Sai viết `\begin{choiceTF} {…}{…}{…}{…} \end{choiceTF}` (cũng `choice`, `choiceTFt`) nay được nhận là **Đúng/Sai** (trước đây bị xếp nhầm vào tự luận).
- Lưu ý: kho MyLT cũ (kiểu trước năm 2025) hầu như không có câu Đúng/Sai nên bảng thống kê ghi 0 là đúng dữ liệu.

## Có gì mới ở bản 0.17.30 – Kèm sẵn mẫu Header của MyLT
- Thư mục `TEMPLATE` có thêm **`Header_MyLT.tex`** (đầu đề kiểu MyLT: `\usepackage[book]{ex_test}`, `\tieude`, `\chantrang`, `\tieudea…d`, `\hetde`, `\heva`, `\hoac`). Chọn ở ô «Kiểu file main có sẵn» khi tạo đề.

## Có gì mới ở bản 0.17.29 – Đọc thẳng công thức MathType, tab «Trộn đề» giống MyLT
- **Công thức MathType (đối tượng OLE) trong file Word được chuyển thẳng sang LaTeX**, không cần Word/MathType: app đọc dữ liệu MTEF trong file (phân số `\dfrac`, căn, mũ/chỉ số, ngoặc, **hệ phương trình `\heva{…}` / `\hoac{…}`**, tổng/tích/tích phân có cận, `\lim`, vectơ, gạch ngang, ma trận, chữ Hy Lạp, ký hiệu…). Kết quả ghi «Đã đọc trực tiếp N công thức MathType». Công thức nào không đọc được thì để `[công thức]` và ghi chú. (Mới kiểm tra bằng công thức dựng theo đặc tả MTEF 5; chưa thử với đủ loại công thức thật – bạn gửi file thì tôi soát tiếp.)
- Chuyển Word: không còn **gạch chân nhầm** «Câu N», «Lời giải», «Trả lời» khi chúng chỉ được tô màu; tên file/thư mục kết quả không còn **dấu cách và dấu tiếng Việt** (trước đây làm `\includegraphics` và pdflatex lỗi).
- **Tab «Trộn đề» theo MyLT 2026**: thanh nguồn ⦿ *Từ ngân hàng câu hỏi* / ○ *Từ Files* (chọn một hoặc nhiều file; câu được nạp vào kho tạm để chọn và trộn), nút *Mở ngân hàng*, *Nhập câu hỏi*; các trang con **Tạo đề theo ID · Tạo đề tự chọn · Tạo đề theo file · Tạo đề tương tự · Tuỳ chọn đề**.
- **Tạo đề theo ID**: khung *Chọn nhanh* (Lớp, Môn, Chương, Bài, Dạng, Mức độ, Loại, Số câu → *Lọc*, *Lấy*) và bảng *Chọn theo ID* (STT, ID dạng `0D0?1-1`, Lớp, Môn, Chương, Bài/dạng, Loại TN/ĐS/SA, Đã có N/H/V/C, số câu cần lấy từng mức).
- **Tạo đề tự chọn**: bảng các câu trong nguồn (lọc theo loại, ID, nội dung) để chọn nhiều dòng đưa vào giỏ đề.

## Có gì mới ở bản 0.17.28 – Sửa lỗi «Failed to load Python DLL … python312.dll» sau khi tự cập nhật
- Sau khi tự cập nhật, bản mới được mở lên kế thừa biến môi trường của bản cũ nên dùng nhầm thư mục giải nén tạm `_MEIxxxx` đã bị xoá. Nay phần mềm bỏ các biến đó (và đặt `PYINSTALLER_RESET_ENVIRONMENT=1`) và chờ vài giây trước khi mở lại.
- Nếu đang gặp lỗi này: đóng thông báo lỗi rồi **bấm đúp lại NganHangDe.exe** (mở mới hoàn toàn thì chạy bình thường); nếu vẫn lỗi, xoá các thư mục `_MEI…` trong `%TEMP%` hoặc thêm phần mềm vào danh sách loại trừ của diệt virus.

## Có gì mới ở bản 0.17.27 – Hộp «Tuỳ chọn chuyển Word/PDF sang TeX» giống MyLT
- Viết lại phần chuyển Word/PDF → LaTeX theo đúng bố cục hộp thoại MyLT 2026: **Hiện Word**; cách đọc **Convert Equations / Toggle TeX / Mathpix API / Gemini** (thêm «Đọc trực tiếp» – không cần Word); tuỳ chọn **Chuyển hình, Chuyển bảng, Chuyển câu ĐS, Chuyên đề, Môn Hoá**; khung **Thông tin Mathpix API** (ID, Key, HDSD, Lưu) và **Thông tin Gemini AI** (API, HDSD, Lưu); bảng **Thay thế cá nhân** (STT, Thay, Bởi; nút ? A D S); nút **Đổi tên** (mẫu tên file kết quả).
- **Một cửa cho Word và PDF**: Tệp → «Chuyển Word/PDF → LaTeX…» và nút «Word/PDF → LaTeX…» (Tiện ích) đều chọn được `.docx` lẫn `.pdf`; kết quả vào `DATA\WORD2EXTEST` / `DATA\PDF2TEX`; xong có nút nhập vào kho (3 bước).
- Mathpix/Gemini với file Word: Word xuất PDF trước (cần Word), rồi gửi từng trang; với file PDF gửi thẳng.
- Tuỳ chọn «Chuyển câu ĐS» tắt thì các ý a) b) c) d) giữ trong đề bài.

## Có gì mới ở bản 0.17.26 – Viết lại luồng chuyển Word → LaTeX
- **Ba cách đọc** trong hộp «Tuỳ chọn Word → TeX»: (1) đọc trực tiếp file Word (nhanh, công thức Word thường); (2) **Word → PDF → Mathpix**; (3) **Word → PDF → AI Gemini/Claude**. Hai cách sau dùng Word xuất PDF (không gọi lệnh MathType nên không dính lỗi MathType) rồi đọc cả công thức MathType từ hình; cần Word trên máy và khoá Mathpix/AI. Word không xuất được PDF thì tự quay về đọc trực tiếp.
- **Luôn hiện kết quả rõ ràng** sau khi chuyển: từng file ra bao nhiêu câu, lưu ở đâu, vì sao 0 câu; lỗi từng file không làm dừng cả lô. Ra 0 câu thì ghi `chan_doan_<tên>.txt`.
- Một hàm dùng chung cho cả «Word → LaTeX» (Tiện ích) và «Nhập file Word» (Tệp).

## Có gì mới ở bản 0.17.25 – Chuyển Word: tự ghi báo cáo chẩn đoán khi ra 0 câu
- Khi chuyển Word → LaTeX mà không nhận dạng được câu hỏi nào (hoặc file có công thức MathType dạng đối tượng), phần mềm ghi file **`chan_doan_<tên>.txt`** vào `DATA\WORD2EXTEST`: số công thức Word/MathType, hình, bảng, đoạn đánh số tự động, những dòng chữ app đọc được và nhận dạng được (Câu N, A–D, a–d…). Gửi file này để biết chính xác vì sao.

## Có gì mới ở bản 0.17.24 – Chuyển Word → LaTeX đọc được đề đánh số tự động
- Nhận **danh sách đánh số tự động của Word**: «Câu 1.», «Câu 2:», phương án A. B. C. D., ý a) b) c) d) vốn không nằm trong văn bản của đoạn (trước đây các đề này ra 0 câu). Đáp án gạch chân/tô màu vẫn nhận đúng.
- **Phương án xếp trong bảng** (4 ô A–D, 1×4 hay 2×2) được dàn lại thành một câu trắc nghiệm, kể cả khi tắt «Chuyển bảng».

## Có gì mới ở bản 0.17.23 – Đọc kho MyLT qua Access Database Engine 64-bit
- Nạp kho MyLT trên Windows: thử PowerShell 32-bit (Jet 4.0) trước, **không được thì thử PowerShell 64-bit** với «Microsoft Access Database Engine» đã cài (nhà cung cấp ACE.OLEDB.12.0). Lỗi của cả hai cách được ghi lại trong bảng chẩn đoán.

## Có gì mới ở bản 0.17.22 – Tab «Cập nhật» (tự cập nhật bản mới)
- Tab mới **⬆ Cập nhật** (cạnh «Thông tin»): bản đang dùng, lần kiểm tra gần nhất, ghi chú bản mới nhất, nút **Kiểm tra bản mới**, **Tải và cập nhật** (thanh tiến trình, kiểm tra SHA-256), **Bỏ qua bản này**, **Mở trang Releases**.
- Tuỳ chọn **Tự kiểm tra khi mở phần mềm** và **Tự tải bản mới về ngay khi có** (cài khi bạn đồng ý khởi động lại).
- Menu «Cập nhật phần mềm…» chuyển sang tab này.

## Có gì mới ở bản 0.17.21 – Sửa lỗi tự cập nhật mở cửa sổ đen `find "…"` và bị treo
- Trình tự cập nhật không còn dùng lệnh `tasklist | find` (khi chạy ngầm chúng mở cửa sổ đen và có thể treo mãi): nay chỉ thử chép đè file exe, phần mềm còn chạy thì Windows từ chối nên chờ rồi thử lại (tối đa ~90 giây), xong tự mở lại.
- **Nếu đang kẹt cửa sổ đen cũ**: mở Task Manager, tắt `find.exe` và `cmd.exe`, xoá `%TEMP%\capnhat_nganhangde.bat`, rồi chép tay file NganHangDe.exe mới nhất từ trang Releases đè lên file cũ.

## Có gì mới ở bản 0.17.20 – Thư mục gói lệnh LaTeX: file xuất ra luôn biên dịch được
- Thư mục mới **`TEMPLATE\\GOI LENH`**: chép vào đây **ex_test.sty bản mới nhất** và các gói riêng (.sty, .cls, .def…). Menu **Công cụ → Cài gói ex_test / gói lệnh LaTeX…** chép giúp.
- Biên dịch trong phần mềm dùng các gói ở thư mục này; **có ex_test.sty thật ở đây thì không dùng gói rút gọn** đi kèm.
- Mọi file xuất ra (đề, lời giải, quyển chuyên đề, từng thư mục mã đề…) được **chép kèm các gói này**, nên mở bằng TeXstudio/Overleaf/máy khác vẫn biên dịch được ngay.
- Xem PDF nhanh ghi file tạm vào `TEMP\\build` (như MyLT).
- Cần bạn chép file `ex_test.sty` bản mới nhất của bạn vào thư mục gói lệnh (phần mềm chưa kèm sẵn vì không phải của phần mềm này).

## Có gì mới ở bản 0.17.19 – Chuyển Word: không treo Word khi MathType lỗi, sửa `$$…$$`
- Khi lệnh MathType trong Word lỗi hoặc kẹt hộp thoại («You cannot close Microsoft Word because a dialog box is open»), phần mềm **tự đóng cửa sổ Word do nó mở** sau 90 giây (không đụng các file Word khác của bạn) và báo cách làm tay; chuyển Word vẫn chạy tiếp bằng bộ đọc có sẵn.
- Ô «Dùng Word + MathType» được ghi rõ là thử nghiệm; hướng dẫn đổi công thức MathType tay (MathType → Convert Equations… → Equations to TeX) rồi chuyển file .docx.
- Công thức nằm giữa câu viết `$$…$$` (MathType «Convert to TeX») tự đổi thành `$…$` khi chuyển Word và trong «Làm sạch code» (Tiện ích 2); công thức trình bày riêng một dòng vẫn giữ `$$…$$`.

## Có gì mới ở bản 0.17.18 – File LaTeX chuyển từ Word lưu vào DATA\\WORD2EXTEST
- Chuyển Word → LaTeX (Tiện ích 1 và Tệp → Nhập file Word): file `<tên>_tuWord.tex` và thư mục hình `<tên>_tuWord_hinh` được lưu vào `DATA\\WORD2EXTEST` thay vì cạnh file Word.

## Có gì mới ở bản 0.17.17 – Tự tải pandoc
- **Công cụ → Tải pandoc (để xuất file Word)**: tải pandoc từ GitHub về thư mục `pandoc` cạnh phần mềm (không cần quyền quản trị, không cần cài bản .msi), có thanh tiến trình và nút Dừng. Khi bấm «LaTeX → Word» mà chưa có pandoc, app hỏi và tải luôn.
- Ô «File Word .docx mỗi mã đề» khi trộn đề không còn bị khoá; chưa có pandoc thì tooltip chỉ cách tải.
- Chưa thử tải thật trên máy Windows (đã thử bằng file zip giả).

## Bản 0.17.16 – như 0.17.15 (nạp kho MyLT lớn nhanh hơn, có tiến trình và nút Dừng); sửa bài kiểm thử trên Windows để bản đóng gói được.

## Có gì mới ở bản 0.17.15 – Nạp kho MyLT lớn nhanh hơn, không còn «treo»
- Bước đọc kho bằng bộ máy Access (Windows) dùng vòng lặp C# thay cho PowerShell từng dòng – nhanh hơn nhiều lần với kho hàng trăm nghìn câu (nếu máy không biên dịch được thì tự quay về cách cũ).
- Hộp thoại hiện rõ **Bước 1/2 – đang đọc kho (đã xuất … MB)** và **Bước 2/2 – đang nhập (đã xử lý … câu)**; nút **Dừng** dùng được ở cả hai bước.

## Có gì mới ở bản 0.17.14 – Sửa lỗi build, xem PDF và Mathpix không cần thêm thư viện
- Sửa lỗi làm bản 0.17.11–0.17.13 không đóng gói được: bộ kiểm thử trên Windows dùng thư viện Pillow mà bản đóng gói không có. Xem PDF trong app và gửi trang cho Mathpix nay vẽ bằng Qt, không cần numpy/Pillow. **Các tính năng của 0.17.11–0.17.13 (phiếu TLTN 2025, Excel TNMaker mặc định, PDF → LaTeX) có trong bản này.**

## Có gì mới ở bản 0.17.13 – PDF → LaTeX (3 cách đọc)
- **Tệp → Chuyển PDF → LaTeX** (và nút «PDF → LaTeX» ở Tiện ích 1): chọn cách đọc – **chữ trong PDF** (miễn phí, không cần mạng), **Mathpix** (chữ + công thức, cả bản chụp) hoặc **AI** Gemini/Claude. Nhận dạng «PHẦN I/II/III», «Câu N», phương án A–D, ý a–d (Đúng/Sai), trả lời ngắn, tự luận và **bảng đáp án ở cuối đề** (tự điền `\True`). Câu chưa có đáp án được ghi chú `%[CHƯA CÓ ĐÁP ÁN]`. Kết quả vào `DATA\PDF2TEX`, có nút nhập thẳng vào kho (3 bước).
- Chuyển Word → LaTeX vẫn như bản trước (công thức Word, gạch chân đáp án, Đúng/Sai, trả lời ngắn).
- Lưu ý: cách «chữ trong PDF» thường mất/đổi công thức; Mathpix chưa thử với khoá thật.

## Có gì mới ở bản 0.17.12 – Trộn đề xuất kèm phiếu và Excel đáp án
- Mỗi lần trộn đề, thư mục kết quả **luôn có**: file đề + lời giải từng mã, **Excel đáp án TNMaker** (`dap_an_TNMaker.xlsx`, bố cục MyLT/TNMaker 2024) và **phiếu TLTN THPT QG 2025** (phiếu trắng + phiếu khoá từng mã, thư mục `phieu_TLTN_2025`). Cả hai đã được tick sẵn; bỏ tick ở tab Phiếu chấm nếu không cần.

## Có gì mới ở bản 0.17.11 – Phiếu TLTN THPT QG 2025 tô sẵn đáp án
- Tuỳ chọn **«Phiếu TLTN THPT QG 2025»** (tab Phiếu chấm khi tạo đề): dùng đúng file phiếu của Bộ (40 câu nhiều lựa chọn · 8 câu Đúng/Sai · 6 câu trả lời ngắn), xuất **phiếu trắng** và **phiếu khoá tô sẵn đáp án + mã đề** cho từng mã đề (PDF, thư mục `phieu_TLTN_2025`). Đáp án trả lời ngắn quá 4 ký tự (kể cả dấu) hoặc mã đề quá 3 chữ số được ghi vào `CANH_BAO.txt`.
- Vị trí ô tô đo từ chính file phiếu; kiểm tra bằng hình, nhưng chưa thử bằng máy quét/phần mềm chấm thật.

## Có gì mới ở bản 0.17.10 – Thư mục như MyLT 2026, Excel đáp án đúng mẫu MyLT, nhập kho rất lớn
- **Bố cục thư mục giống MyLT 2026**: `DATA\\BANK`, `DATA\\DE` (đề trộn), `DATA\\EXAM`, `DATA\\AUTO`, `DATA\\MA TRAN DE`, `DATA\\TUONG TU`, `DATA\\WORD2EXTEST`, `DATA\\EXTEST2WORD`, `DATA\\PDF2TEX`, `DATA\\MOODLE XML`, `DATA\\MFORMS`, `DATA\\PDF QUIZ`, `DATA\\LOC ID`, `DATA\\LOC TIKZ`, `DATA\\IMG`, cùng `TEMPLATE`, `Map ID (DPS)`, `TEMP`, `LOG`. Các hộp thoại mở/lưu tự trỏ vào đúng thư mục. Máy đang dùng thư mục tên cũ (`de_xuat`, `mau_de`…) vẫn chạy, không tự di chuyển dữ liệu.
- **Excel đáp án kiểu MyLT / TNMaker 2024** (theo file mẫu `11A2-LAN1-HOCKI1_DA_TNMaker2024.xlsx`): sheet «MyLT», số câu liên tục, mã đề ở hàng 1 (là kiểu mặc định).
- **Nhập kho MyLT rất lớn** (đã thử với kho 206.066 dòng): câu có LaTeX hỏng được bỏ qua và ghi lại thay vì dừng cả lần nhập.
- Đi kèm file `Phiếu TLTN THPT QG 2025 (1 mặt).pdf` trong `DATA` (phiếu trả lời trắc nghiệm mẫu).

## Có gì mới ở bản 0.17.9 – Trộn đề đầy đủ hơn (theo MyLT)
- **Ẩn/hiện đáp án bằng 1 lệnh**: tuỳ chọn «Đưa đáp án vào một môi trường» – bảng đáp án nằm trong `\\ifshowans … \\fi`, đổi `\\showanstrue`/`\\showansfalse` là ẩn/hiện.
- **Trộn riêng từng vùng** theo lớp, môn, chương, mức độ hoặc bài (theo ID của câu) – tab Trộn trong «Tuỳ chọn trộn đề».
- **Lọc câu khi tạo đề**: chỉ lấy câu có lời giải, hoặc chỉ câu chưa có lời giải.
- **Đề tương tự**: mở rộng tìm theo ID5 / ID4 / ID3 khi thiếu câu cùng ID; chọn câu giống nội dung nhất.
- **Tạo đề theo ID**: lọc theo chương (ẩn bài các chương khác).
- **Trộn theo file**: nhiều file một lúc, `file.tex:số câu` để lấy ngẫu nhiên từng file.
- **Kiểu file main**: chọn nhanh các file .tex trong thư mục `mau_de` (chép thêm file vào đó là có thêm lựa chọn).

## Có gì mới ở bản 0.17.8 – Kho MyLT lớn (hàng trăm nghìn câu), dọn kho
- **Công cụ → Dọn kho**: ① lọc câu trùng (giống hệt hoặc gần giống), **chỉ giữ lại 1 câu** mỗi nhóm (ưu tiên câu có lời giải, ID đầy đủ); ② lọc câu sai (lỗi LaTeX/đáp án khi rà soát). Xem danh sách trước khi xoá; câu xoá khôi phục được.
- **Nhập kho MyLT lớn**: đọc từng dòng, ghi theo lô, có thanh tiến trình và nút Dừng; kho trên 60 MB không dùng bộ đọc chậm. Trên Windows bộ OLEDB cho phép chạy tới 3 giờ (chưa thử với kho thật).

## Có gì mới ở bản 0.17.7 – Nhập 3 bước, xem PDF trong app, giao diện, Mathpix (theo bản Gemini)
- **Tệp → Nhập .tex 3 bước**: ① rà soát (bắt buộc có lời giải/đáp án, bỏ trùng, trùng sâu, không nhập ID 5 ký tự, bỏ câu lỗi) → ② AI giải lại câu có vấn đề → ③ nhập vào kho; có nút xuất .tex đã sửa.
- **Xem PDF ngay trong app** (nút trong hộp kết quả biên dịch): lật trang, phóng to/thu nhỏ.
- **Công cụ → Giao diện & Mathpix**: đổi màu chủ đạo, màu nhấn, cỡ chữ; nhập khoá Mathpix; **Ảnh → LaTeX bằng Mathpix** (chưa thử với khoá thật).

## Có gì mới ở bản 0.17.6 – Nhập Word có tuỳ chọn, nhiều mẫu phiếu, kiểu mã QR (theo bản Gemini)
- **Word → TeX có hộp thoại tuỳ chọn**: bảng, hình ảnh, lý thuyết, công thức hoá học, bảng thay thế "cũ = mới"; tuỳ chọn chuyển công thức MathType qua Word (chưa thử trên máy có Word – cần phản hồi).
- **Mẫu phiếu trả lời**: kiểm tra số câu theo phiếu BGD 2025 (40·8·6), Toán rút gọn (12·4·6), HSG (30·10·10), KHTN (16·3·12), TNMaker 40/60; cảnh báo cả độ dài mã đề.
- **Kiểu mã QR đáp án**: gọn, `MD:…;P1:…;P2:…;P3:…`, hoặc JSON.
- Chưa làm: phiếu TLTN 2025 chèn PDF, AI rà soát giải lại, xem PDF trong app, Mathpix.

## Có gì mới ở bản 0.17.5 – Quyển chuyên đề, Tiện ích 2 đầy đủ hơn (theo bản Gemini và MyLT)
- **Xuất quyển chuyên đề** (Tiện ích → Xuất & chuyển đổi): gom câu hỏi theo chương – bài – dạng (tên lấy từ Map ID), có trang bìa, mục lục, đề + lời giải; xuất .tex hoặc biên dịch PDF luôn.
- **Tiện ích 2** thêm: chèn `\dapso{đáp án}`, trộn thứ tự câu trong file, trộn phương án trong file, sắp xếp câu theo ID, gán một ID cho cả file, xoá ID / in ID sau câu / bỏ ID đã in.

## Bản 0.17.4 – Đọc kho MyLT bền hơn, nhập Word không cần pandoc
- **Kho MyLT**: khi nhập `Bank.mylt` bị lỗi hoặc ra 0 câu, bấm *Chi tiết* trong thông báo để xem **báo cáo chẩn đoán** (đọc bằng cách nào, bảng/cột/số dòng) – gửi báo cáo này cho người hỗ trợ là sửa được ngay.
- **Tự đồng bộ kho MyLT**: sau lần nhập đầu, mỗi lần mở phần mềm, nếu file `Bank.mylt` có thay đổi thì tự thêm các câu mới (chỉ thêm, không xoá/sửa câu đã có).
- **Nhập file Word (.docx) không cần cài pandoc**: phần mềm tự đọc Word bằng Python – công thức Word (OMML) sang LaTeX, bảng, hình, đáp án **gạch chân hoặc tô màu** (cách MyLT), báo số công thức MathType (đối tượng OLE) nếu có. Máy có pandoc thì vẫn dùng pandoc như cũ.

## Bản 0.17.3 – Đọc kho MyLT bằng bộ máy Access của Windows
- **Đọc `Bank.mylt` chắc chắn hơn trên Windows**: phần mềm mở file bằng chính Microsoft Jet (OLEDB) qua PowerShell 32-bit có sẵn trong Windows, **tự lấy mật khẩu của file Access** (MyLT đặt `MyLT@2018` trong phần đầu file) – không cần cài Access. Nếu cách này không chạy được thì tự quay về cách đọc cũ (không cần mật khẩu). Ý tưởng cách đọc lấy từ bản Gemini thầy/cô gửi.
- Thư mục `gemini_v4.6/` trong kho GitHub: bản Gemini lưu để đối chiếu (không đóng gói vào phần mềm).

## Bản 0.17.2 – Có sẵn ngân hàng mẫu để dùng thử
- **Nạp ngân hàng mẫu** (Tệp → Nạp ngân hàng mẫu): khoảng **100 câu** gồm 22 câu Toán 10 (đề mẫu có ID, đáp án, lời giải) và các câu đổi số hàm số Toán 12 có hình, lời giải – thử trộn đề, rà soát, vẽ hình ngay khi chưa có dữ liệu riêng. Nạp nhiều lần không bị nhân đôi.
- **Mở phần mềm khi kho trống** sẽ hiện hướng dẫn 3 cách có dữ liệu: nhập kho MyLT, nhập file .tex, hoặc nạp ngân hàng mẫu.

## Bản 0.17.1 (gồm cả 0.17.0) – Bổ sung theo MyLT 2018: nhập kho MyLT, file header, câu đổi số tự động, Tiện ích 2
- **Dùng ngân hàng MyLT** (menu Tệp):
  - **Nhập ngân hàng MyLT**: chọn `Bank.mylt` (hoặc `Bank.rar` có mật khẩu – phần mềm hỏi, mặc định MyLT123, cần WinRAR hoặc 7-Zip trên máy) → toàn bộ câu hỏi chuyển sang kho mới, giữ ID, câu tự luận, **số lần đã lấy ra đề**; câu trùng tự bỏ qua. Không cần cài Microsoft Access;
  - **Tìm kho MyLT trên máy**: tự tìm mọi file `Bank.mylt` (Desktop, Tài liệu, Tải xuống, ổ C:–H:), hiện số câu và dung lượng từng file để chọn;
  - **Mở kho câu hỏi** chọn thẳng file `.mylt`/`.rar` cũng được nhập luôn;
  - nhận nhiều kiểu đặt tên bảng/cột của các phiên bản MyLT khác nhau. Lưu ý: kho mẫu đi kèm bản cài MyLT **trống** – kho thật nằm ở máy đang dùng MyLT.
- **Dùng file header của MyLT** làm mẫu đề: chép `Header.tex`, `Header1.tex`… vào thư mục `mau_de`, chọn ở ô *File mẫu .tex* (nút ▾). Phần mềm tự điền tên trường, kì thi, môn, thời gian, gọi `\tieude`, `\chantrang`, tiêu đề từng phần `\tieudea…\tieuded`, `\hetde` – đề ra đúng bố cục quen thuộc.
- **Chuyển nhanh Map ID**: chép các file Map ID (Map ID_Goc, _HSG, _3Sach…) vào thư mục `map_id`, chọn ở Giải nghĩa ID → *Map ID trong thư mục map_id ▾*.
- **Câu đổi số tự động** (tab Soạn thảo, không cần AI): 10 dạng Toán 12 – đơn điệu (công thức, bảng biến thiên, đồ thị), cực trị, số điểm cực trị hàm trùng phương, tìm m để đạt cực đại, GTLN/GTNN trên đoạn, tiệm cận, nhận dạng đồ thị; mỗi câu có ID, 4 phương án, hình và lời giải.
- **Tiện ích 2**: xoá dòng trống/căn mã, đặt đáp án theo chuỗi, đưa đáp án đúng về A, chuyển mức độ trong ID (5 mức cũ → 4 mức), tách file theo chương/bài/dạng, nối file, tạo mã `\input`, xuất cả kho ra các file theo ID.
- **Mỗi mã đề một thư mục** (Tuỳ chọn trộn đề → Trình bày).
- Thư mục **`nhat_ky`**: khi phần mềm gặp lỗi, chi tiết được ghi vào `nhat_ky.txt`.
- **Giao diện dễ nhìn hơn**: tab chính chữ to đậm, tab con có viền cam đánh dấu tab đang chọn; các tab vừa màn hình 1366 px.
- Sửa: mẫu đề mặc định thiếu gói `tkz-tab` (câu có bảng biến thiên không biên dịch được); nhãn đạo hàm trong bảng biến thiên ghi `f'(x)`.

## Bản 0.16.2 – Thư mục phần mềm gọn gàng như MyLT
Lần đầu chạy, phần mềm tạo các thư mục con ngay cạnh file `NganHangDe.exe`:

```
NganHangDe\
├── NganHangDe.exe
├── config.ini     ← cài đặt (không còn lưu trong Registry)
├── DOC_TOI.txt    ← giải thích các thư mục
├── du_lieu\       ← kho câu hỏi nganhang.db
├── mau_de\        ← de_thi.tex (sửa theo mẫu của trường là có hiệu lực ngay), gói ex_test rút gọn
├── map_id\        ← danh mục ID Toán 6–12 (.tex)
├── de_xuat\       ← đề đã trộn
├── sao_luu\       ← bản sao lưu kho
├── anh\           ← ảnh PNG
├── online\        ← bài online, trình chiếu, Google Forms
└── tam\           ← file tạm (xoá thoải mái)
```
- **Chép nguyên thư mục này sang máy khác hoặc USB là dùng được ngay**, giữ đủ kho câu hỏi và cài đặt.
- Máy đang dùng bản cũ: cài đặt cũ tự chép sang `config.ini`, kho cũ (`nganhang.db` cạnh exe) vẫn được dùng tiếp, không mất gì.
- Menu **Tệp → Mở thư mục phần mềm**; tab **Thông tin** ghi rõ đường dẫn.
- Nếu đặt phần mềm trong thư mục không ghi được (vd `C:\Program Files`), dữ liệu tự chuyển sang `%LOCALAPPDATA%\NganHangDe`.

## Bản 0.16.1 – Biên dịch bằng LaTeX của TeXstudio (TeX Live 2019…)
- Phần mềm **đọc cài đặt của TeXstudio** trên máy: TeXstudio dùng pdflatex/xelatex ở đâu thì phần mềm dùng đúng chỗ đó – máy chỉ có TeX Live + TeXstudio (không cần MiKTeX) vẫn biên dịch PDF được.
- Tìm TeX Live mọi năm (2019 → `bin\win32`, 2023 trở đi → `bin\windows`) ở mọi ổ đĩa `C:\texlive`, `D:\texlive`, …
- *Công cụ → Cài đặt biên dịch PDF → Kiểm tra* cho biết đang dùng trình biên dịch nào (ghi rõ «theo cài đặt TeXstudio»). Vẫn chỉ tay được đường dẫn, vd `C:\texlive\2019\bin\win32\pdflatex.exe`.

## Bản 0.16.0 – Câu đổi số AI, lời giải AI, chọn đề theo bảng ID, kết quả online về Google Form
- **Câu đổi số AI** (Trợ lý AI, hoặc nút 🤖 trong tab **Soạn thảo**): giữ nguyên câu chữ, dạng câu, cách giải – chỉ đổi số liệu; AI tính lại đáp án, đổi phương án nhiễu và viết lại lời giải. Câu mới được rà soát tự động, giáo viên duyệt rồi mới đưa vào kho / trang soạn thảo.
- **Lời giải AI**: AI tự giải từng câu, viết lời giải vào `\loigiai` (câu chưa có lời giải, hoặc viết lại cả câu đã có) và **so đáp án AI tìm được với đáp án đang đánh dấu** – câu lệch được báo đỏ để kiểm tra lại (AI không tự sửa đáp án).
- **Trộn đề → Chọn theo ID**: bảng mọi dạng (lớp – môn – chương – bài – dạng) có trong kho, số câu sẵn có từng mức Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao; gõ số câu muốn lấy từng mức (không vượt quá số câu có), lọc theo lớp, loại, tên dạng, «đã lấy / chưa lấy», điền nhanh mỗi dạng N câu → **Tạo đề ngay** hoặc đưa vào ma trận.
- **Sắp xếp câu trong mỗi phần**: ngẫu nhiên, theo thứ tự dòng ma trận, hoặc theo ID.
- **Bài online / Blogger gửi kết quả về Google Form** (xem điểm cả lớp trong Google Trang tính): Tiện ích → Xuất & chuyển đổi → *Màu & Google Form nhận kết quả*. Dán «đường liên kết điền sẵn» của Form (các ô điền từ khoá TEN, LOP, SBD, DIEM…), phần mềm tự đọc mã các ô. Đổi được màu khung, nền, chữ câu, chữ lời giải.
- **Google Forms dạng ảnh**: mỗi câu được biên dịch thành ảnh PNG (công thức hiện chuẩn) + file Apps Script dựng Form từ thư mục ảnh trên Google Drive (cần MiKTeX/TeX Live).
- **Lưu ý:** các chức năng gửi tới Google (Form, Apps Script) và AI chưa được thử với tài khoản thật – lần đầu dùng nên thử với một đề nhỏ.

## Bản 0.15.0 – Bố cục theo nhóm chức năng, bổ sung theo MyLT 2026
Cửa sổ chính chia thành 10 tab: **Trộn đề · Câu hỏi · Ma trận · Tiện ích · Vẽ hình · Đồ thị · BBT & Xét dấu · Biểu diễn nghiệm · Soạn thảo · Thông tin**.
- **Trộn đề** có 4 cách:
  - *Theo ma trận ID* (như cũ);
  - *Tự chọn câu*: nhặt từng câu vào «giỏ đề», sắp thứ tự rồi trộn;
  - *Theo file*: trộn thẳng file .tex; thêm dòng `%VUNG` để **trộn theo vùng** (câu chỉ đổi chỗ trong vùng);
  - *Đề tương tự*: từ một đề mẫu, mỗi câu được thay bằng câu cùng ID trong kho (mỗi mã đề một bộ khác nhau nếu muốn).
- **Tuỳ chọn trộn đề** thêm: mã đề cách nhau N; tỉ lệ đáp án A:B:C:D; trộn/không trộn câu trả lời ngắn; giữ ý d) cố định ở câu Đúng/Sai; đáp án ở cuối file đề; chèn trang trống cho đủ số trang chẵn (in 2 mặt); **phiếu trả lời** (phiếu trắng + phiếu tô sẵn đáp án từng mã).
- **Câu hỏi:** cột **Diễn giải ID**; cây chi tiết tới bài, dạng; nút **Từ file…** để xem/lọc câu trong file .tex mà không cần nạp vào kho, rồi **Nạp vào kho** nếu muốn.
- **Ma trận:** bảng theo CV 7991 cập nhật ngay theo ma trận đang soạn, điểm từng phần, báo dòng kho còn thiếu, nút bù câu thiếu bằng AI.
- **Tiện ích → Xuất & chuyển đổi:** Moodle, **Aiken**, **Quizizz** (Excel), **Microsoft Forms** (Word, nhập nhanh), Google Forms, **Blogger**, bài làm online; **phiếu trả lời** (trắng, tô theo đề, tô theo chuỗi đáp án); **hoá ảnh hình TikZ** (PNG); **đề LaTeX gõ thường → ex_test**; Word ↔ LaTeX; trình chiếu.
- **Vẽ hình:** **dựng hình phẳng theo từng bước** (điểm, trung điểm, giao điểm, chân đường vuông góc, trọng tâm, tâm ngoại/nội tiếp, phép quay, đoạn, đường thẳng, đa giác, đường tròn, elip, đường cong, kí hiệu góc vuông, cung góc, đoạn bằng nhau, tô miền, chữ), xem trước ngay, sửa/đổi thứ tự/xoá bước, lưu và mở lại; 8 hình mẫu; hình khối.
- **Đồ thị:** 15 mẫu hàm số thường gặp; **đồ thị theo cực trị** (bậc ba, trùng phương); giá trị tuỳ chọn trên Ox, Oy (kể cả π/2, π); **điểm gióng**.
- **BBT & Xét dấu:** thêm **bảng xét dấu** tự động (tích, thương, đa thức) hoặc nhập tay.
- **Biểu diễn nghiệm:** trục số, miền nghiệm, **đường tròn lượng giác** (gõ `pi/6 + k2pi` → các điểm ngọn cung).
- **Soạn thảo:** soạn đề với nút chèn nhanh câu TN, Đúng/Sai, trả lời ngắn, tự luận, công thức; rà soát; biên dịch PDF; nạp vào kho.
- **Thông tin:** phiên bản, kiểm tra cập nhật, hướng dẫn.
- Sửa: phím tắt Ctrl+I bị trùng (Nhập file .tex và Trợ lý AI) – Trợ lý AI nay là Ctrl+Shift+I. Nhận «Đáp án: B» đặt sau các phương án khi chuyển Word/LaTeX thường sang ex_test.

## Bản 0.14.0 – Giai đoạn 4: phòng thi LAN, Google Forms, trình chiếu, bộ cài
- **Phòng thi LAN** (Đề thi → Phòng thi LAN): máy giáo viên phát đề qua Wi-Fi, học sinh làm bài trên điện thoại/máy tính (không cần cài gì, **không cần Internet**). Trang làm bài **không chứa đáp án** – máy giáo viên chấm, xem **bảng điểm trực tiếp**, mở bảng điểm lên máy chiếu, xuất CSV.
- **Trình chiếu chữa đề** (Đề thi → Trình chiếu, F11): mỗi câu một trang toàn màn hình, phím A hiện đáp án, L hiện lời giải, **B bút vẽ** lên màn hình, T bấm giờ, N nền tối. Cũng xuất được cùng lúc với đề (tab Online / Word).
- **Google Forms:** xuất file Apps Script (.gs) – dán vào script.google.com, bấm Chạy là có bài kiểm tra trên Google Form (công thức đổi sang chữ thường; Đúng/Sai tách 4 câu; trả lời ngắn chấm tay – giới hạn của Google Forms).
- **Moodle:** nhúng ảnh (`\includegraphics`) vào file XML; câu tự luận có đáp án cho người chấm và điểm theo thang điểm.
- **Cây dữ liệu** bên trái chi tiết tới **bài** và **dạng** (tên lấy từ Map ID).
- **Bộ cài đặt** và **bản thư mục** (xem đầu trang).
- MathJax đi kèm phần mềm: trình chiếu và phòng thi LAN hiện công thức không cần Internet.
- Dòng lệnh: `arena de.tex -n 4`, `slides de.tex -o trinh_chieu.html`.

## Bản 0.13.0 – Giai đoạn 3: Trợ lý AI nhiều nhà cung cấp, Draw Studio
- **Chọn nhà cung cấp AI** (Công cụ → Cài đặt AI): Google Gemini (có hạn mức miễn phí), Anthropic Claude, OpenAI, DeepSeek, Grok. Mỗi nhà cung cấp lưu khoá riêng; nút *Kiểm tra kết nối* tải danh sách mô hình.
- **Trợ lý AI** (Câu hỏi → Trợ lý AI, Ctrl+I):
  - **Câu tương tự:** chọn câu trong kho → AI soạn câu mới cùng dạng, cùng ID, có lời giải (tuỳ chọn khó hơn một mức);
  - **Bù câu thiếu ma trận:** dòng ma trận nào kho chưa đủ câu thì AI soạn thêm cho đủ;
  - **PDF → LaTeX:** đề PDF (kể cả bản chụp) chuyển sang ex_test, mỗi lần 10 trang (Gemini hoặc Claude); hình được đánh dấu để vẽ lại;
  - **Chấm tự luận:** dán bài làm hoặc chọn PDF bản chụp, AI chấm theo barem từng ý (điểm gợi ý, giáo viên quyết định).
  - Mọi câu AI soạn đều được **rà soát tự động** và hiện ra để **duyệt trước khi thêm vào kho**; câu có lỗi được bỏ chọn sẵn.
- **Hỏi AI cách sửa lỗi biên dịch:** trong hộp kết quả biên dịch PDF có nút 🤖 – AI chỉ nguyên nhân và dòng cần sửa.
- **Gán ID bằng AI** dùng được với mọi nhà cung cấp, không chỉ Gemini.
- **Draw Studio** (tab Vẽ hình):
  - **Trục số:** gõ `(-inf;-2] U (1;3) U {5}` → hình biểu diễn tập nghiệm, gạch bỏ phần không thuộc;
  - **Miền nghiệm** hệ bất phương trình bậc nhất hai ẩn, kèm **toạ độ các đỉnh và GTLN, GTNN của F = ax + by**;
  - **Đồ thị:** tự vẽ **tiệm cận đứng, ngang, xiên**; **tô miền tích phân** trên [a; b] (giữa đồ thị và Ox, hoặc giữa hai đồ thị);
  - **Hình khối:** hình chóp tứ giác đều, chóp có SA ⊥ đáy, chóp tam giác, tứ diện, lăng trụ, hình hộp, lập phương, nón, trụ, cầu (cạnh khuất nét đứt);
  - nút **Xem trước PDF**.
- **Lưu ý:** chức năng AI cần Internet và khoá API của nhà cung cấp; nội dung câu hỏi được gửi tới nhà cung cấp đó. AI có thể giải sai – luôn kiểm tra lại.
- Chưa làm: chuyển công thức **MathType** trong Word (đối tượng OLE) – cần chính MathType để đọc, chưa có cách làm tin cậy.

## Bản 0.12.0 – Giai đoạn 2: ma trận CV 7991, thang điểm, phiếu chấm
- **Ma trận theo Công văn 7991** (tab Tạo đề → *Ma trận CV 7991…*):
  - xuất **Excel** (hoặc **Word**, cần pandoc) với hàng là chủ đề, cột là 4 dạng câu × Biết/Hiểu/Vận dụng, tổng số câu, điểm, tỉ lệ;
  - sheet *Dòng ma trận* sửa được rồi **nạp lại** bằng *Mở ma trận…* (chọn file .xlsx).
- **Thang điểm tuỳ chỉnh** (Tuỳ chọn trộn đề → tab *Thang điểm*): điểm Phần I, Phần III, thang Phần II (đúng 1/2/3/4 ý), điểm từng câu tự luận. Áp dụng cho thang điểm in trong lời giải, bài online, Moodle, file đáp án.
- **Câu chùm luôn đi liền nhau:** gắn nhãn `%[chum:TÊN]` cho các câu cùng chùm → khi trộn đề chúng đứng liền và giữ thứ tự.
- **Không quá 3 câu liền nhau cùng đáp án** (đổi được, 0 = tắt), vẫn giữ cân bằng A/B/C/D.
- **Phiếu chấm** (tab *Phiếu chấm*):
  - ngoài TNMaker, điền đáp án **theo file mẫu của bất kì phần mềm chấm nào** (QM, Azota, SmartTest…): chọn file mẫu .xlsx do phần mềm đó xuất ra, phần mềm tự tìm ô «Mã đề»/«Câu» và nhãn câu rồi điền đúng chỗ;
  - **mã QR đáp án** in cuối file lời giải;
  - sau khi tạo đề, **kiểm tra đề có vừa phiếu trả lời mẫu 2025** (40 · 8 · 6 câu) và đáp án trả lời ngắn có tô được không.
- Dòng lệnh: `make … --qr --mau-phieu mau.xlsx --max-run 3`, khoá `"diem"` trong file ma trận; lệnh mới `matrix ma_tran.json -o mt.xlsx`.

## Bản 0.11.0 – Nâng cấp giai đoạn 1 (theo bản nghiên cứu 2026)
- **Kho tự nâng cấp an toàn:** lần đầu mở kho cũ, phần mềm **tự sao lưu** thành `nganhang.db.bak` rồi mới nâng cấp. Dữ liệu cũ giữ nguyên.
- **Tìm kiếm không dấu, nhanh hơn:** gõ `tap nghiem` vẫn tìm được «tập nghiệm» (dùng chỉ mục toàn văn FTS5).
- **Hỗ trợ ex_test 3.3:** giữ đúng `\choiceTF`, `\choiceTFt`, `\shortans`, `\dapso` khi nạp và xuất lại.
- **Danh mục ID Toán 6–12 có sẵn** (1 504 mục, từ Map ID của thầy/cô):
  - kho mới tự nạp sẵn, không cần làm gì;
  - trong **Giải nghĩa ID**: nút *Nạp danh mục có sẵn* và *Xuất trang tra cứu HTML* (tìm không dấu, bấm để chép mã).
- **Lịch sử ra đề** (menu **Đề thi → Lịch sử ra đề**): mỗi lần tạo đề được ghi lại (tên, mã đề, số câu, thư mục); nhấp đúp để mở thư mục.
- **Tránh lặp câu giữa các bài kiểm tra:** tab Tạo đề có ô *Tránh câu đã dùng trong N đợt gần nhất*.
- **Rà soát theo CV 1239:**
  - trả lời ngắn quá 4 kí tự, dạng phân số, có chữ hoặc đơn vị → báo **Lỗi**;
  - câu Đúng/Sai có cả 4 ý cùng Đúng (hoặc cùng Sai) → cảnh báo;
  - ảnh `\includegraphics` không tìm thấy → báo lỗi;
  - nhận thêm phương án kiểu «Cả A và B», «Các đáp án trên» → không trộn phương án đó.
- Giao diện được tách thành nhiều phần nhỏ để dễ bảo trì; exe gọn hơn (bỏ các thành phần Qt không dùng).

## Bản 0.10.0 – Tự cập nhật phiên bản, mở bằng TeXstudio
- **Tự cập nhật** (menu **Trợ giúp → Cập nhật phần mềm**):
  - xem ghi chú bản mới, bấm **⬇ Tải và cập nhật ngay**;
  - phần mềm tải exe mới (có thanh tiến trình) và **kiểm tra mã SHA-256** để chống file hỏng;
  - sau đó tự đóng, thay bản mới, rồi **tự mở lại**. Bản cũ được giữ lại thành `NganHangDe_cu.exe`.
- **Tự kiểm tra bản mới mỗi khi mở phần mềm** (tắt được). Có nút *Bỏ qua bản này*.
- **TeXstudio:**
  - **Câu hỏi → Mở câu đã chọn trong TeXstudio** (Ctrl+T);
  - nhấp đúp file biên dịch lỗi → mở TeXstudio **đúng dòng bị lỗi**;
  - mở đề vừa tạo, mở file trong tab Công cụ.
  Phần mềm tự tìm TeXstudio; chỉ đường dẫn được trong *Cài đặt biên dịch PDF*. Máy không có TeXstudio thì mở bằng chương trình mặc định.
- **Lưu ý:** bản 0.9.0 trở về trước chưa có chức năng tự cập nhật, nên cần tải tay bản 0.10.0 một lần. Từ bản này trở đi, phần mềm tự cập nhật.

## Bản 0.9.0 – Gán ID tự động bằng Gemini (AI)
- **🤖 Gán ID bằng Gemini:**
  - menu **Câu hỏi → Gán ID tự động bằng Gemini** (Shift+F3), hoặc nút 🤖 trong hộp Gán ID;
  - Gemini đọc đề bài, phương án, lời giải và chọn **chương › bài › dạng trong Map ID của thầy/cô**, đánh giá luôn **mức độ** N/H/V/C kèm **độ tin cậy** và **lí do**;
  - phần mềm **đối chiếu lại với Map ID**: mã Gemini tự nghĩ ra (không có trong Map ID) bị loại.
- Kết quả điền vào cột «ID mới» để thầy/cô **duyệt trước khi lưu** (vào kho hoặc ra file .tex mới).
- Chọn **phạm vi** (ví dụ chỉ lớp 10) để gửi ít Map ID hơn, cho nhanh và đỡ tốn hạn mức.
- **Cài đặt:** menu **Công cụ → Cài đặt Gemini**.
  - Dán khoá API miễn phí lấy tại aistudio.google.com/apikey, bấm *Kiểm tra kết nối* để tải danh sách mô hình (nên chọn bản «flash»).
  - Khoá lưu trên máy của thầy/cô.
- **Lưu ý:** nội dung câu hỏi được gửi tới máy chủ Google; cần Internet.
- Dòng lệnh: `set GEMINI_API_KEY=…` rồi `python -m nganhangde ai-id de.tex --scope 0 -o de_ganID.tex`.

## Bản 0.8.0 – Biên dịch PDF
- **📄 Xem PDF câu đã chọn** (nút trên thanh công cụ, phím F5): chọn một hoặc nhiều câu trong kho, phần mềm biên dịch và mở PDF có lời giải. Hộp «Sửa câu» cũng có nút *Xem PDF*.
- **Tạo đề → tick «Biên dịch luôn ra PDF»:** sau khi trộn, mọi file đề và lời giải được biên dịch thành PDF. Chạy ở luồng nền nên phần mềm không bị treo; có thanh tiến trình và nút Huỷ.
- **Biên dịch file .tex bất kì** (menu Công cụ hoặc tab Công cụ). File chỉ có câu hỏi sẽ tự được bọc vào mẫu đề.
- **Báo lỗi dễ hiểu kèm số dòng**, ví dụ «Dòng 4: lệnh không tồn tại», «thiếu dấu $», «ngoặc { } không cân bằng», «thiếu gói …». Nhấp đúp để mở file.
- **Tự tìm MiKTeX / TeX Live** trên máy (pdflatex → xelatex → lualatex). Menu **Công cụ → Cài đặt biên dịch PDF**: chọn trình biên dịch, chỉ đường dẫn, thư mục chứa `ex_test.sty`, số lượt chạy; nút *Kiểm tra* cho biết máy đã đủ gói chưa.
- **Chưa cài gói ex_test vẫn biên dịch được:** phần mềm dùng **gói rút gọn đi kèm**, tự chia phương án thành 4, 2 hoặc 1 cột, tô đỏ đáp án ở bản lời giải. Muốn bản in chính thức thì cài ex_test thật.
- **Mẫu đề chạy được cả pdflatex** (gói tiếng Việt vntex) **lẫn xelatex** (phông Times New Roman, không có thì dùng phông dự phòng).
- Sửa lỗi mẫu đề: bỏ trống ô «Sở/Phòng GD» làm pdflatex báo lỗi. Gọi LaTeX hay pandoc không còn bật cửa sổ đen trên Windows.
- Cần cài **MiKTeX** (miễn phí, miktex.org) hoặc TeX Live. Dòng lệnh: `python -m nganhangde pdf de.tex`, hoặc thêm `--pdf` khi trộn đề.

## Bản 0.7.0 – Sinh câu hỏi số và vẽ hình (đợt 3, 4)
**🔢 Sinh câu (tab mới)**
- Từ **một câu mẫu có tham số**, sinh hàng loạt biến thể với số liệu khác nhau. Đáp án và lời giải tự tính theo số mới.
- Khai báo biến bằng dòng `%@`:
  - `%@ a = 1..9` (số nguyên), `%@ b = -5..5 khac 0` (loại trừ giá trị), `%@ c = [2,3,5]` (chọn trong danh sách);
  - `%@ D = b*b-4*a*c` (biểu thức), `%@ dk: D > 0` (điều kiện).
- Trong câu viết `@{biểu thức}` để chèn giá trị. Có sẵn hàm `frac`, `dec`, `term`, `coef`, `sq`, `C`, `A`…
- Mỗi biến thể được rà soát (đáp án, lời giải, LaTeX) và loại câu trùng. Có 2 câu mẫu để bắt đầu (trắc nghiệm, trả lời ngắn).

**🎨 Vẽ hình (tab mới)** – sinh mã TikZ, xem trước ngay trong phần mềm
- **Bảng biến thiên** (`tkz-tab`): nhập hàm số là tự tính đạo hàm, cực trị, giới hạn, tiệm cận đứng (đa thức, phân thức…). Sửa tay được.
- **Đồ thị hàm số:** chọn khung x, y, lưới, đánh dấu điểm; tự tách nhánh ở chỗ hàm không xác định.
- **Biểu đồ cột và biểu đồ quạt** từ bảng số liệu.

## Bản 0.6.0 – Đề online, Moodle, Word ↔ LaTeX (đợt 2)
- **Bài làm online:** mỗi mã đề một file HTML, mở bằng trình duyệt trên máy tính, iPhone hoặc Android.
  - Học sinh nhập tên, làm bài có đồng hồ đếm ngược, bấm *Nộp bài* là được chấm ngay theo thang điểm thi tốt nghiệp.
  - Sau khi nộp: hiện đáp án đúng/sai từng câu và (tuỳ chọn) lời giải. Gửi qua Zalo hoặc email được.
  - Cần mạng khi mở để hiện công thức. Dùng để ôn tập, không dùng cho kì thi chính thức.
- **Moodle XML:** trắc nghiệm → multichoice; Đúng/Sai → cloze 4 ý; trả lời ngắn → shortanswer (nhận cả 0,5 và 0.5).
- **LaTeX → Word (.docx):** công thức thành công thức Word gốc, sửa được bằng Equation.
- **Word → LaTeX:**
  - nhận dạng «Câu 1.», phương án A–D (cùng dòng hay mỗi dòng một phương án đều được), ý a)–d) kể cả danh sách đánh số tự động;
  - đáp án lấy từ chữ cái **gạch chân**; nhận cả «Đáp án: …» và «Lời giải: …»;
  - nhập thẳng vào kho (menu Tệp → Nhập file Word).
- Thẻ **«Online / Word»** trong Tuỳ chọn trộn đề; menu **Tệp → Xuất câu ra Word / Moodle / bài làm online**; tab Công cụ có Word → LaTeX, LaTeX → Word, Bài làm online từ file.
- **Chức năng Word cần cài pandoc** (miễn phí): https://pandoc.org/installing.html (bản Windows .msi).

## Bản 0.5.0 – Bổ sung theo MyLT (đợt 1)
**Tạo đề**
- **Đổi câu trước khi trộn:** tick «Xem trước bộ câu…». Bấm *🎲 Đổi ngẫu nhiên* hoặc *Chọn câu thay…*; câu thay luôn cùng dòng ma trận.
- **Xếp câu dễ → khó** trong mỗi phần (Nhận biết → Vận dụng cao), ở thẻ «Trộn».
- **Giới hạn tỉ lệ câu trùng** giữa 2 mã đề, khi mỗi mã dùng một bộ câu khác.
- **Thông tin đầu đề:** Sở/Phòng GD, kì thi, môn, năm học, giáo viên. Mẫu đề mới có ô Họ tên, Số báo danh và dòng «HẾT».
- **In ma trận đặc tả** (Excel hoặc LaTeX), kèm tên chương/bài/dạng lấy từ Map ID.
- Thẻ «Trình bày» có thêm: in ID nhỏ sau mỗi câu trong file lời giải (bản giáo viên), nén cả kết quả thành `.zip`.

**Ngân hàng câu hỏi**
- **Lịch sử sửa từng câu**, khôi phục được bản cũ; **khôi phục câu đã xoá** (menu Câu hỏi).
- **Tìm và thay thế** hàng loạt (Ctrl+H) trong đề bài, phương án, lời giải; có hỗ trợ regex.
- **Lọc theo nguồn**, **tìm câu gần trùng** theo tỉ lệ %, xoá câu thừa.
- **Kiểm tra bản cập nhật** (menu Trợ giúp).

**Công cụ trên file .tex**
- Tìm và thay thế, xoá ID, xoá một nguồn, lọc câu theo nguồn, trích hình TikZ ra file riêng, tìm câu gần trùng.

## Bản 0.4.0 – Tuỳ chọn trộn đề và đáp án cho TNMaker
- Mục **«Tuỳ chọn trộn đề»** (tab Tạo đề) gồm 4 thẻ:
  - **Mã đề:** đánh mã liên tiếp hoặc ngẫu nhiên, chọn mã bắt đầu, 3 hoặc 4 chữ số (0101…).
  - **Trộn:** trộn câu, trộn phương án, trộn ý Đúng/Sai, cân bằng đáp án A/B/C/D, giữ đề gốc.
  - **Trình bày:** đánh số lại từ Câu 1 ở mỗi phần, tiêu đề và lời dẫn theo mẫu đề thi tốt nghiệp, in thang điểm trong file lời giải.
  - **Phiếu chấm TNMaker:** xuất `dap_an_TNMaker.xlsx`. Chọn được bố cục (mỗi dòng 1 câu hoặc mỗi dòng 1 mã đề), phần Đúng/Sai gộp hay tách 4 ô, kí hiệu Đ/S, T/F hoặc 1/0, dấu thập phân. File có thêm sheet «Thông tin» (cấu trúc, thang điểm) và sheet «Mã đề – câu gốc».
- **Nút ⭐ Áp dụng chuẩn đề thi tốt nghiệp THPT 2026:**
  - 12 câu trắc nghiệm, 4 câu Đúng/Sai, 6 câu trả lời ngắn; 90 phút; 24 mã đề 0101…0124;
  - giữ thứ tự ý Đúng/Sai, đánh số lại từng phần, lời dẫn chính thức, thang điểm, đáp án Excel;
  - báo khi ma trận lệch cấu trúc 12 – 4 – 6.
- Trộn đề trực tiếp từ file (tab Công cụ) dùng chung các tuỳ chọn này. Dòng lệnh có thêm `--chuan-2026`.
- Sửa lỗi ngầm khi thêm dòng vào ma trận đề.

## Bản 0.3.0 – Map ID và gán ID
- **Nạp thẳng file Map ID dạng gạch ngang** (`Map_ID.tex` dùng chung với các phần mềm khác) vào menu **Công cụ → Giải nghĩa ID**. Phần mềm báo các mã bị khai báo trùng và xuất lại được đúng định dạng đó.
- **Gán ID cho nhiều câu** (nút 🏷 Gán ID, phím F3; với file thì vào tab Công cụ → Gán ID cho file):
  - **Gợi ý ID tự động** theo câu giống nhất trong kho và theo tên chương/bài/dạng trong Map ID, có hiện độ giống;
  - **Nhận gợi ý tốt nhất** cho các câu có độ giống từ ngưỡng chọn trở lên;
  - **Chọn ID theo Map ID** (Lớp → Môn → Chương → Bài → Dạng → Mức độ) rồi áp cho các câu đã chọn; chỉ đổi Mức độ cũng được;
  - Lưu vào kho, hoặc lưu thành file `.tex` mới (file gốc giữ nguyên).
- Gợi ý chỉ để tham khảo: hãy xem lại cột «ID mới» trước khi lưu.

## Bản 0.2.0 – Rà soát và tự sửa
- **Tự sửa đáp án lệch lời giải.** Chọn tin vào lời giải (sửa đánh dấu `\True`) hoặc tin vào đáp án (sửa chữ «Chọn X», «Đúng/Sai» trong lời giải).
- **Thêm câu kết luận còn thiếu:** «Chọn đáp án X» cho trắc nghiệm, «Vậy đáp án là …» cho trả lời ngắn.
- **Đổi dấu chấm thập phân** trong đáp án trả lời ngắn thành dấu phẩy.
- **Nút ⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI.** Một bước sửa mọi câu sửa được, rồi bỏ những câu vẫn còn lỗi. Với file `.tex`, kết quả lưu thành file mới; file gốc giữ nguyên.
- Cột **«Tự sửa được»** cho biết trước phần mềm sẽ sửa gì ở từng câu.
- **Sửa lỗi khi trộn đề:** chữ «Chọn X» trong lời giải nay tự đổi theo vị trí mới của phương án.

## Chức năng chính
- Ngân hàng câu hỏi LaTeX (`ex_test`): trắc nghiệm, Đúng/Sai, trả lời ngắn, tự luận; phân loại theo ID `[0D2N1-2]`, giải nghĩa ID, câu tương tự.
- Tạo đề theo ma trận, nhiều mã đề, cân bằng đáp án A/B/C/D, ma trận từ đề có sẵn.
- Rà soát đáp án, lời giải và lỗi LaTeX; tự sửa và bỏ câu sai.
- Công cụ trên file `.tex`: trộn đề trực tiếp, lọc/đổi ID, lấy bảng đáp án, tìm câu trùng.
- Sao lưu, gộp và tách kho.
