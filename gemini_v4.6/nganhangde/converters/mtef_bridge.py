"""Cầu nối xử lý công thức MathType OLE (oleObject*.bin / MTEF) chuẩn MyLT 2026."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile


@dataclass
class MtefObjectInfo:
    entry_name: str
    size_bytes: int
    is_ole_cfb: bool
    mtef_version: int | None


def inspect_docx_mtef_objects(docx_path: str) -> list[MtefObjectInfo]:
    """Quét toàn bộ word/embeddings/oleObject*.bin trong .docx để nhận diện MathType OLE/MTEF."""
    results: list[MtefObjectInfo] = []
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if not (name.startswith("word/embeddings/oleObject") and name.endswith(".bin")):
                continue
            blob = zf.read(name)
            is_cfb = blob.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
            mtef_ver: int | None = None
            if b"Equation Native" in blob or b"MathType" in blob:
                mtef_ver = 5
            results.append(MtefObjectInfo(name, len(blob), is_cfb, mtef_ver))
    return results


def convert_mathtype_via_word_com(
    docx_path: str | Path,
    out_docx: str | Path,
    show_word: bool = True,
    mode: str = "toggle_tex",
) -> tuple[bool, str]:
    """Dùng Microsoft Word + MathType Add-in (Toggle TeX / Alt+\\) trên Windows để đổi toàn bộ MathType -> LaTeX."""
    if os.name != "nt":
        return False, "Word COM chỉ hỗ trợ trên Windows."

    src = Path(docx_path).resolve()
    dst = Path(out_docx).resolve()
    shutil.copy2(src, dst)

    ps = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ps_code = r"""param([string]$DocPath, [string]$ShowWord, [string]$Mode)
$ErrorActionPreference = "Stop"
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $true
    $word.DisplayAlerts = 0
    try { $word.Activate() } catch {}

    # Đảm bảo MathType Add-in (.dotm / .dot) trong thư mục STARTUP của Word đã được nạp
    $startupDirs = @(
        (Join-Path $env:APPDATA "Microsoft\Word\STARTUP"),
        "C:\Program Files (x86)\MathType\Office Support\32",
        "C:\Program Files (x86)\MathType\Office Support\64",
        "C:\Program Files\MathType\Office Support\64"
    )
    foreach ($sd in $startupDirs) {
        if (Test-Path $sd) {
            Get-ChildItem -Path $sd -Filter "MathType*.dot*" -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $already = $false
                    foreach ($ai in $word.AddIns) {
                        if ($ai.Name -eq $_.Name) { $ai.Installed = $true; $already = $true }
                    }
                    if (-not $already) { $word.AddIns.Add($_.FullName, $true) | Out-Null }
                } catch {}
            }
        }
    }

    $doc = $word.Documents.Open($DocPath)
    $doc.Activate()
    try { $word.ActiveWindow.Activate() } catch {}
    $beforeShapes = $doc.InlineShapes.Count
    $word.Selection.WholeStory()

    $ran = $false
    $macros = @(
        "MTCommand_ToggleTeX",
        "MTTeXToggle.Main",
        "UIWrappers.MTCommand_ToggleTeX",
        "MathTypeCommands.UIWrappers.MTCommand_ToggleTeX",
        "MathTypeCommands.MTCommand_ToggleTeX"
    )
    foreach ($m in $macros) {
        try {
            $word.Run($m)
            $ran = $true
            break
        } catch {}
    }

    # Nếu không gọi được macro trực tiếp, gửi tổ hợp phím Alt+\ (Toggle TeX chuẩn của MathType)
    if (-not $ran) {
        $wshell = New-Object -ComObject WScript.Shell
        try { $wshell.AppActivate($word.Caption) | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        $wshell.SendKeys("%\\")
        $ran = $true
    }

    # Chờ MathType hoàn tất chuyển đổi (tối đa 45 giây)
    for ($t = 0; $t -lt 90; $t++) {
        Start-Sleep -Milliseconds 500
        $curShapes = 0
        try { $curShapes = $doc.InlineShapes.Count } catch {}
        if ($beforeShapes -gt 0 -and $curShapes -lt $beforeShapes) {
            Start-Sleep -Milliseconds 1500
            break
        }
        if ($t -ge 8 -and $beforeShapes -eq 0) { break }
    }

    $afterShapes = $doc.InlineShapes.Count
    $doc.Save()
    if ($beforeShapes -gt 0 -and $afterShapes -ge $beforeShapes) {
        Write-Output "UNCHANGED:$beforeShapes"
    } else {
        Write-Output "OK:$beforeShapes->$afterShapes"
    }
} finally {
    if ($null -ne $doc) {
        try { $doc.Close($false) } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch {}
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    for ($w = 0; $w -lt 20; $w++) {
        try {
            $fs = [System.IO.File]::Open($DocPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $fs.Close()
            break
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
}
"""
    with tempfile.TemporaryDirectory(prefix="mt_com_") as td:
        ps_file = Path(td) / "mt_toggle.ps1"
        ps_file.write_text(ps_code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [
                    ps,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps_file),
                    str(dst),
                    "1" if show_word else "0",
                    mode,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=180,
            )
            out_s = proc.stdout.decode("utf-8", errors="replace").strip()
            err_s = proc.stderr.decode("utf-8", errors="replace").strip()
            if proc.returncode == 0 and "OK:" in out_s:
                return True, f"Đã chuyển công thức MathType qua Word ({out_s})."
            if "UNCHANGED:" in out_s:
                return False, f"Word đã mở nhưng MathType chưa đổi công thức ({out_s}). Hãy kiểm tra MathType Add-in trong Word hoặc chọn chế độ 'Dùng Gemini'."
            return False, err_s or out_s or "Không chạy được MathType trong Word."
        except Exception as exc:
            return False, str(exc)


def convert_docx_to_pdf_via_word_com(docx_path: str | Path, out_pdf: str | Path) -> tuple[bool, str]:
    """Xuất nhanh .docx sang .pdf bằng Microsoft Word COM (phục vụ nhánh Gemini AI OCR khi chọn 'Dùng Gemini')."""
    if os.name != "nt":
        return False, "Word COM chỉ hỗ trợ trên Windows."
    src = Path(docx_path).resolve()
    dst = Path(out_pdf).resolve()
    ps = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ps_code = r"""param([string]$DocPath, [string]$PdfPath)
$ErrorActionPreference = "Stop"
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($DocPath, $false, $true)
    $doc.ExportAsFixedFormat($PdfPath, 17)
    Write-Output "OK"
} finally {
    if ($null -ne $doc) { try { $doc.Close($false) } catch {} }
    if ($null -ne $word) { try { $word.Quit() } catch {} }
}
"""
    with tempfile.TemporaryDirectory(prefix="w2pdf_") as td:
        ps_file = Path(td) / "w2pdf.ps1"
        ps_file.write_text(ps_code, encoding="utf-8")
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            proc = subprocess.run(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file), str(src), str(dst)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                creationflags=creationflags,
            )
            if proc.returncode == 0 and dst.exists():
                return True, str(dst)
            return False, proc.stderr.decode("utf-8", errors="replace").strip() or "Lỗi xuất PDF từ Word."
        except Exception as exc:
            return False, str(exc)


def convert_omml_docx_to_mathtype_ole(in_docx: str, out_docx: str) -> bool:
    """Gọi omml-converter (Python 3.12+) để chuyển OMML -> MathType 5.0 OLE thuần Python."""
    exe = shutil.which("omml-converter")
    if not exe:
        return False
    proc = subprocess.run([exe, in_docx, "-o", out_docx], capture_output=True, text=True)
    return proc.returncode == 0
