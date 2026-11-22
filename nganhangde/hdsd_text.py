"""Nội dung HDSD (cửa sổ «HDSD», như phần mềm MyLT 2026). Mỗi mục: (nhóm, tiêu đề, nội dung HTML ngắn gọn).
Tên nút, tên tab khớp đúng giao diện hiện tại. Thêm/sửa mục ở đây, không cần sửa giao diện."""

TOPICS = [
    ("Bắt đầu", "Bắt đầu nhanh", """
<ol>
<li><b>Mở kho:</b> Tệp → Mở kho câu hỏi (hoặc Tạo kho mới). Phần mềm nhớ kho lần trước.</li>
<li><b>Có câu chưa:</b> Nhập file .tex (Tệp → Nhập file .tex…) hoặc nút <b>Nhập câu hỏi</b> ở tab Trộn đề.</li>
<li><b>Gán ID</b> cho câu chưa có ID (xem mục «Gán ID và Map ID»).</li>
<li><b>Trộn đề:</b> vào tab <b>Trộn đề</b>, chọn nguồn, chọn cách tạo đề, đặt tuỳ chọn, bấm <b>Tạo đề</b>.</li>
<li>Kết quả nằm trong thư mục <code>DATA\\DE</code> (xem mục «Kết quả và thư mục»).</li>
</ol>
<p>Mẹo: <b>F1</b> mở HDSD này.</p>"""),

    ("Kho câu hỏi", "Mở, tạo, sao lưu kho", """
<ul>
<li><b>Mở kho câu hỏi…</b> (Ctrl+O): chọn file .db hoặc kho MyLT (.mylt/.rar – sẽ nhập vào kho đang mở).</li>
<li><b>Tạo kho mới…</b> (Ctrl+N): tạo file .db trống.</li>
<li><b>Sao lưu kho…</b> (Ctrl+B): lưu một bản .db. Nên sao lưu trước khi xoá hoặc dọn kho nhiều.</li>
<li><b>Gộp kho khác vào kho này…</b>: thêm câu từ kho khác, câu trùng được bỏ qua.</li>
<li><b>Tách câu đã chọn ra kho mới…</b>: chép các câu đang chọn sang kho mới.</li>
<li><b>Khôi phục câu đã xoá…</b>: đưa lại câu đã xoá (xoá không mất hẳn).</li>
</ul>"""),

    ("Kho câu hỏi", "Nhập câu hỏi vào ngân hàng", """
<p>Nút <b>Nhập câu hỏi</b> ở tab Trộn đề (khi nguồn là ngân hàng).</p>
<ol>
<li>Bấm <b>Chọn</b> để chọn file .tex (hoặc <b>Thêm</b> để nối thêm file).</li>
<li>Tick tuỳ chọn: <i>Không nhập câu ID5</i> (câu chưa phân dạng), <i>Bỏ qua câu trùng</i>, <i>Kiểm tra câu trùng</i>, <i>Kiểm tra câu trùng sâu</i> (chọn <b>Tỉ lệ</b> giống nhau, mặc định 85%).</li>
<li><b>Nhập</b>: mở màn rà soát 3 bước – xem từng câu, bỏ câu lỗi, rồi nhập.</li>
</ol>
<p><b>Kiểm tra</b>: chỉ quét và báo số câu sai, câu trùng; <b>không xoá gì</b>.<br>
<b>Xoá lỗi</b>: xoá các câu sai sau khi bạn xác nhận (có thể khôi phục).<br>
<b>Xuất</b>: ghi toàn bộ câu trong kho ra file .tex.<br>
<b>Khởi tạo</b>: tạo kho trống mới. <b>Khôi phục</b>: mở lại một bản sao lưu.</p>"""),

    ("Kho câu hỏi", "Nguồn câu: Từ ngân hàng và Từ Files", """
<ul>
<li><b>Từ ngân hàng câu hỏi</b> (mặc định): các tab trộn đề lấy câu từ kho đang mở. Nút <b>Mở ngân hàng</b> đổi kho và nạp luôn.</li>
<li><b>Từ Files</b>: chọn một hoặc nhiều file .tex (nút <b>Chọn files…</b>). Câu được nạp vào kho tạm trong bộ nhớ, <b>không ghi vào kho chính</b>.</li>
<li><b>Nạp câu hỏi</b> (🔄): đọc lại nguồn đang chọn – dùng khi bạn vừa sửa file hoặc đổi kho.</li>
<li>Ở tab <b>Tạo đề theo file</b>, nút <b>Nạp vào nguồn</b> cũng chuyển sang chế độ Từ Files với các file đã chọn.</li>
</ul>"""),

    ("Kho câu hỏi", "Tab Câu hỏi", """
<ul>
<li>Cây bên trái: lọc theo Lớp → Môn → Chương → Bài → Dạng. Ô phía trên: Loại, Mức độ, ID, nội dung.</li>
<li><b>Thêm câu mới</b> (menu Câu hỏi), <b>Sửa câu</b> (F2), <b>Xoá câu</b> (Delete): tác động lên dòng đang chọn.</li>
<li><b>Gán ID</b> (F3): gán ID cho câu đã chọn hoặc câu thiếu ID. <b>Gán ID tự động bằng AI</b> (Shift+F3) cần cài khoá AI.</li>
<li><b>Xem PDF</b> (F5), <b>Mở trong TeXstudio</b> (Ctrl+T): xem câu đã chọn.</li>
<li><b>Xuất câu…</b>: xuất câu đang chọn ra .tex (Ctrl+E); <b>Xuất câu ra Word / Moodle / bài làm online</b> cho định dạng khác.</li>
<li><b>Tìm và thay thế</b> (Ctrl+H): thay chuỗi trong nhiều câu.</li>
</ul>"""),

    ("Gán ID", "Gán ID và Map ID", """
<ul>
<li>ID dạng <code>0D2N1-2</code>: lớp (0=10, 1=11, 2=12) · môn (D=Đại số, H=Hình) · chương · mức độ (N/H/V/C) · bài · sau dấu «-» là dạng.</li>
<li><b>Map ID</b> (Ctrl+M, Giải nghĩa ID…): đặt tên cho chương, bài, dạng để hiện đẹp trong bảng chọn. Mặc định đã có Map ID Toán 6–12.</li>
<li>Muốn nạp Map ID mới: chép file .tex vào thư mục <code>Map ID (DPS)</code> rồi bấm <b>Nạp lại (Map ID)</b> trong tab Trộn đề.</li>
</ul>"""),

    ("Ma trận", "Tab Ma trận", """
<ul>
<li>Lập ma trận đề: mỗi dòng là một loại câu (TN, ĐS, SA, TL), mẫu ID (có thể dùng <code>*</code> và <code>?</code>), mức độ và số câu.</li>
<li>Cột <b>Kho có</b> cho biết kho đủ câu cho dòng đó chưa.</li>
<li>Lưu/mở ma trận dạng file; in ma trận đặc tả; xuất ma trận CV 7991.</li>
</ul>"""),

    ("Trộn đề", "Tạo đề theo ID", """
<ol>
<li>Phần <b>Chọn nhanh</b>: chọn Lớp, Môn, Chương, Bài, Dạng, Mức độ, Loại, Số câu rồi bấm <b>Lọc</b>, sau đó <b>Lấy</b>.</li>
<li>Phần <b>Chọn theo ID</b>: bảng mỗi dòng là một ID; cột <b>Đã có (N/H/V/C)</b> là số câu kho có. Nhập số vào cột <b>Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao</b>.</li>
<li>Ô <b>Điền nhanh</b>: nhập số, chọn mức độ, bấm <b>Điền</b> để điền cho mọi dòng đang hiện. <b>Xoá số đã nhập</b> để xoá hết.</li>
<li>Các nút chữ <b>? H A C E D O U</b> chọn nhanh một nhóm dòng; <b>Đầu/Trước/Sau/Cuối</b> để chuyển trang.</li>
<li>Bấm <b>Tạo đề</b> (góc dưới) để trộn ngay, hoặc <b>Đưa vào ma trận</b> rồi tạo ở tab Nâng cao.</li>
</ol>
<p>Dòng <b>?</b> là câu chưa có ID hoặc ID không đọc được: vẫn lấy ngẫu nhiên được.</p>"""),

    ("Trộn đề", "Tạo đề tự chọn", """
<ol>
<li>Lọc bằng hàng trên: Lọc, Lớp, Môn, Chương, Bài, Dạng, Mức độ, Loại, Kiểu ID (ID6 có dạng / ID5 không dạng), Đã lấy.</li>
<li>Tick cột <b>Chọn</b> ở từng câu. Tick được giữ khi chuyển trang.</li>
<li>Bấm <b>Chọn [số]</b> để lấy ngẫu nhiên N câu trong danh sách đang lọc; <b>Chọn hết</b> chọn tất cả (tối đa 2000); <b>Xoá chọn</b> bỏ hết.</li>
<li><b>Sửa câu hỏi</b> mở trình sửa câu đang chọn; <b>Xoá</b> xoá câu khỏi kho (sau khi xác nhận).</li>
<li>Tick <b>PDF</b> nếu muốn biên dịch luôn đề thành PDF. Bấm <b>Tạo đề</b>.</li>
</ol>"""),

    ("Trộn đề", "Tạo đề theo file", """
<ol>
<li>Bấm <b>Chọn files…</b> để chọn một hoặc nhiều file .tex đề. Bảng hiện số câu <b>Đã có</b> của mỗi file.</li>
<li>Cột <b>Lấy</b>: nhập số câu lấy ngẫu nhiên từ file đó; để trống là lấy hết.</li>
<li><b>Bỏ file chọn</b>: bỏ các dòng đang chọn. <b>Xoá chọn</b>: xoá các số trong cột Lấy.</li>
<li><b>Nạp vào nguồn</b>: đưa các file này vào nguồn chung của tab Trộn đề (dùng cho bảng ID và Tự chọn).</li>
<li>Bấm <b>Tạo đề</b>. File có dòng <code>%VUNG</code> sẽ được trộn trong từng vùng.</li>
</ol>"""),

    ("Trộn đề", "Tạo đề tương tự", """
<ol>
<li>Bấm <b>Chọn</b> để chọn file đề gốc (.tex).</li>
<li>Đặt <b>Tìm theo</b>: ID (cùng dạng), ID mở rộng (bỏ dạng), hoặc Nội dung. Đặt <b>Tỉ lệ tương tự</b> (chỉ áp dụng khi tìm theo nội dung) và <b>Số đề tối đa</b>.</li>
<li>Bấm <b>Tìm</b>. Chọn <b>Đề tương tự thứ</b> N để xem từng đề.</li>
<li>Bỏ tick <b>Chọn</b> ở câu nào thì giữ câu gốc. <b>Đổi</b> thay câu tương tự ở dòng đang chọn; <b>Sửa</b> sửa câu đó.</li>
<li><b>Lưu</b> ghi đề đang xem ra file .tex. <b>Tạo đề</b> trộn thành các mã đề.</li>
</ol>"""),

    ("Trộn đề", "Tuỳ chọn đề", """
<p>Tab này gồm mọi tuỳ chọn trộn và xuất:</p>
<ul>
<li><b>Số đề tạo ra</b>; <b>Kiểu đề gốc</b> (một đề gốc hoặc mỗi mã một đề gốc); <b>Mã đề cách</b>, <b>Mã đề 3 số</b>, <b>Mã đề tự nhập</b> (ví dụ 132, 209, 357).</li>
<li><b>Sắp xếp câu hỏi</b>: theo lớp, môn, chương, mức độ, bài, dạng. <b>Trộn đề theo vùng</b>: trộn riêng từng vùng.</li>
<li><b>Đáp án Excel</b>: chọn kiểu TNMaker, Bảng dọc, Bảng ngang… để chấm phiếu.</li>
<li><b>Phiếu làm bài</b>: Phiếu TLTN THPT QG 2025 (phiếu trắng + phiếu khoá đáp án từng mã). Tick <b>Chỉ đáp án</b> để chỉ xuất phiếu khoá.</li>
<li><b>Màu vẽ</b>, <b>Nét vẽ</b>: màu và cỡ ô tô trên phiếu khoá.</li>
<li><b>Cài đặt tiêu đề</b>: tên trường, tên kỳ thi, tên môn, giáo viên, thời gian. <b>File header</b>: chọn mẫu đề trong thư mục TEMPLATE.</li>
<li><b>Tên file đề tạo ra</b>: ví dụ <code>KT15p</code> → <code>KT15p_101.tex</code>.</li>
<li><b>Lưu ma trận</b>: lưu ma trận hiện tại với tên bạn đặt.</li>
</ul>
<p>Các ô tick khác trong «Tuỳ chọn phiếu» chỉ lưu cấu hình, chưa dùng khi vẽ phiếu.</p>"""),

    ("Trộn đề", "Nâng cao (ma trận…)", """
<p>Tab này có các phần cũ: Thông tin đề, thư mục xuất, file mẫu .tex, trộn đề, mã đề, trình bày, thang điểm, phiếu chấm, bài làm online/Word, Moodle, Google Forms, trình chiếu. Dùng khi cần tuỳ chỉnh sâu. Nút <b>TẠO ĐỀ</b> ở đây tạo đề theo ma trận.</p>"""),

    ("Trộn đề", "Kết quả và thư mục", """
<ul>
<li>File đề xuất vào <code>DATA\\DE</code>: <code>de_&lt;mã&gt;.tex</code> (đề) và <code>loigiai_&lt;mã&gt;.tex</code> (lời giải).</li>
<li>Đáp án: <code>dap_an.csv</code>, <code>dap_an_TNMaker.xlsx</code>; phiếu TLTN 2025 trong thư mục <code>phieu_TLTN_2025</code>.</li>
<li>Thư mục <code>TEMPLATE\\GOI LENH</code>: gói lệnh LaTeX (ex_test.sty). Phần mềm tự chép gói cạnh file đề.</li>
<li>Thư mục xuất đổi trong tab Nâng cao. Mở nhanh: Tệp → Mở thư mục phần mềm.</li>
</ul>"""),

    ("Công cụ", "Tiện ích, xuất và chuyển đổi", """
<ul>
<li><b>Tiện ích 1 / Tiện ích 2</b>: các công cụ xử lý file .tex hàng loạt (ví dụ tìm và thay thế, xoá ID, xoá nguồn, trộn đề từ file). Mỗi nút có dòng mô tả ngay bên cạnh.</li>
<li><b>Xuất &amp; chuyển đổi</b>: xuất câu ra Word, Moodle, bài làm online, trình chiếu.</li>
<li><b>Rà soát</b>: kiểm tra đáp án và lời giải của đề.</li>
<li><b>Sinh câu</b>: tạo câu mới từ câu mẫu (xem hướng dẫn trong tab).</li>
<li><b>Thống kê</b>: số câu theo lớp, môn, chương, dạng và loại.</li>
<li>Tệp → <b>Nhập file Word (.docx)</b> và <b>Chuyển Word/PDF → LaTeX</b>. Xuất file Word cần pandoc: Công cụ → <b>Tải pandoc</b>.</li>
</ul>"""),

    ("Công cụ", "Dọn kho", """
<ol>
<li>Mở Nhập câu hỏi → <b>Kiểm tra</b> để xem số câu sai và câu trùng (không xoá gì).</li>
<li>Vào Công cụ → <b>Dọn kho</b>: <b>Quét kho</b>, rồi xem danh sách trước khi xoá.</li>
<li>Xoá câu trùng giữ lại 1 câu mỗi nhóm; xoá câu sai theo lỗi khi rà soát.</li>
<li>Mọi lần xoá đều có thể khôi phục ở Câu hỏi → <b>Khôi phục câu đã xoá</b>.</li>
</ol>"""),

    ("Vẽ hình", "Trục số, miền nghiệm, đường tròn lượng giác", """
<ul>
<li><b>Trục số</b> (Biểu diễn nghiệm → Trục số): nhập tập hợp như <code>(-inf;-2] U (1;3) U {5}</code>. Tick <i>Gạch bỏ phần không thuộc tập nghiệm</i> theo kiểu SGK. Bấm <b>Tạo mã</b>.</li>
<li><b>Miền nghiệm</b>: nhập từng bất phương trình mỗi dòng, đặt khung xmin/xmax/ymin/ymax, và biểu thức F (tìm GTLN, GTNN).</li>
<li><b>Đường tròn lượng giác</b>: nhập các họ góc, mỗi dòng một họ; bấm tạo mã.</li>
<li>Sau khi tạo mã, khung bên phải hiện <b>xem trước</b> (cần LaTeX trên máy). Chọn cỡ hình ở ô <b>Cỡ hình</b>.</li>
<li>Các nút dưới: <b>Chép mã</b> (dán vào câu hỏi), <b>Lưu thành file .tex…</b>, <b>Xem trước PDF</b>.</li>
</ul>"""),

    ("Vẽ hình", "Bảng biến thiên và bảng xét dấu", """
<ul>
<li><b>Bảng biến thiên</b> (tab BBT &amp; Xét dấu): nhập hàm số y = …, bấm <b>Tự lập bảng từ hàm số</b>; hoặc sửa tay ba hàng <i>x</i>, <i>y'</i>, <i>y</i> theo cú pháp tkz-tab rồi bấm <b>Tạo mã từ 3 hàng trên</b>.</li>
<li><b>Bảng xét dấu</b>: nhập biểu thức, bấm tạo mã.</li>
<li>Mã dùng gói <code>tkz-tab</code>.</li>
</ul>"""),

    ("Vẽ hình", "Đồ thị và biểu đồ", """
<ul>
<li><b>Đồ thị hàm số</b> (tab Đồ thị): nhập hàm, khoảng vẽ; có mẫu hàm, tiệm cận, tô miền và điểm đặc biệt.</li>
<li><b>Biểu đồ cột / quạt</b>: nhập nhãn và giá trị, chọn kiểu, bấm tạo mã.</li>
<li>Xem trước ở khung bên phải; chỉnh cỡ bằng ô <b>Cỡ hình</b>.</li>
</ul>"""),

    ("Vẽ hình", "Hình khối và hình phẳng", """
<ul>
<li><b>Dựng hình phẳng</b> (Vẽ hình → Dựng hình phẳng): chọn hình, nhập kích thước, bấm tạo mã TikZ.</li>
<li><b>Hình khối</b>: chọn loại hình trong danh sách, nhập chiều cao và kích thước đáy, bấm tạo mã.</li>
</ul>"""),

    ("Soạn thảo", "Soạn thảo và chuyển đổi tài liệu", """
<ul>
<li><b>Soạn thảo</b>: nơi soạn mã LaTeX tự do (đề, lời giải).</li>
<li><b>Chuyển Word/PDF → LaTeX</b> (Tệp): chọn file Word hoặc PDF rồi làm theo các bước trong hộp thoại. File kết quả nằm trong <code>DATA\\WORD2EXTEST</code> hoặc <code>DATA\\PDF2TEX</code>.</li>
<li>Nếu chuyển công thức chưa đúng, mở file kết quả, sửa tay, rồi nhập lại.</li>
</ul>"""),

    ("Cài đặt", "Cài đặt biên dịch PDF, gói LaTeX và AI", """
<ul>
<li><b>Cài đặt biên dịch PDF…</b> (Công cụ): chỉ đường dẫn tới pdflatex/xelatex nếu máy không tự tìm thấy (TeX Live hoặc MiKTeX).</li>
<li><b>Cài gói ex_test / gói lệnh LaTeX</b> (Công cụ): chép file .sty mới nhất vào <code>TEMPLATE\\GOI LENH</code>.</li>
<li><b>Cài đặt AI</b> (Công cụ): khoá Gemini, Claude hoặc OpenAI, cho các tính năng AI.</li>
<li><b>Giao diện &amp; Mathpix</b> (Công cụ): đổi màu, cỡ chữ và khoá Mathpix.</li>
</ul>"""),

    ("Khác", "Cập nhật và giới thiệu", """
<ul>
<li><b>Cập nhật phần mềm…</b> (Trợ giúp, tab ⬆ Cập nhật): kiểm tra và tải bản mới. Phần mềm tự thay bản cũ khi bạn xác nhận.</li>
<li><b>Giới thiệu</b>: phiên bản hiện tại.</li>
</ul>"""),
]
