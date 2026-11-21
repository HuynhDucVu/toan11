"""Vẽ trang PDF thành QImage/PNG bằng pypdfium2 + Qt – không cần numpy hay Pillow (bản .exe không có hai thư viện này)."""
from __future__ import annotations


def render_page(doc, index: int, scale: float = 1.4):
    """Trang `index` của pypdfium2.PdfDocument → QImage (độc lập với bộ nhớ của pdfium)."""
    from PySide6.QtGui import QImage
    bm = doc[index].render(scale=scale)
    ch = bm.n_channels
    fmt = QImage.Format.Format_BGR888 if ch == 3 else QImage.Format.Format_ARGB32
    return QImage(bytes(bm.buffer), bm.width, bm.height, bm.stride, fmt).copy()


def render_file(path: str, index: int = 0, scale: float = 1.4):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        return render_page(doc, index, scale) if 0 <= index < len(doc) else None
    finally:
        doc.close()


def png_bytes(img) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)
