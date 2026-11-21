"""Microsoft Word + MathType (chỉ Windows): đổi công thức MathType (đối tượng OLE) trong file .docx.

Hai chế độ:
* «convert» – dùng lệnh Convert Equations của MathType: MathType → công thức Word (OMML); docxnative đọc được ngay;
* «toggle_tex» – dùng Toggle TeX (Alt+\\) của MathType: công thức thành mã LaTeX nằm trong văn bản.
Cần Word và MathType (có Add-in cho Word) trên máy. Không có thì trả về lỗi dễ hiểu – không làm hỏng file gốc
(luôn làm việc trên bản sao).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

MACROS = {
    "convert": ["MTCommand_ConvertEquations", "MathTypeCommands.UIWrappers.MTCommand_ConvertEquations",
                "MathTypeCommands.MTCommand_ConvertEquations"],
    "toggle_tex": ["MTCommand_ToggleTeX", "MTTeXToggle.Main", "UIWrappers.MTCommand_ToggleTeX",
                   "MathTypeCommands.UIWrappers.MTCommand_ToggleTeX", "MathTypeCommands.MTCommand_ToggleTeX"],
}

PS = r"""param([string]$Src, [string]$Dst, [string]$Visible, [string]$Macros, [string]$SendKeys)
$ErrorActionPreference = "Stop"
$word = $null; $doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = ($Visible -eq "1")
    $word.DisplayAlerts = 0
    foreach ($sd in @((Join-Path $env:APPDATA "Microsoft\Word\STARTUP"),
                      "C:\Program Files (x86)\MathType\Office Support\32", "C:\Program Files (x86)\MathType\Office Support\64",
                      "C:\Program Files\MathType\Office Support\64")) {
        if (Test-Path $sd) {
            Get-ChildItem -Path $sd -Filter "MathType*.dot*" -ErrorAction SilentlyContinue | ForEach-Object {
                try { $word.AddIns.Add($_.FullName, $true) | Out-Null } catch {}
            }
        }
    }
    $doc = $word.Documents.Open($Src)
    $before = $doc.InlineShapes.Count
    $word.Selection.WholeStory()
    $ran = $false
    foreach ($m in ($Macros -split ";")) {
        if ($m -eq "") { continue }
        try { $word.Run($m); $ran = $true; break } catch {}
    }
    if (-not $ran -and $SendKeys -ne "") {
        $sh = New-Object -ComObject WScript.Shell
        try { $sh.AppActivate($word.Caption) | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        $sh.SendKeys($SendKeys); $ran = $true
    }
    if (-not $ran) { throw "NOMACRO: không tìm thấy lệnh MathType trong Word (đã cài MathType và Add-in cho Word chưa?)" }
    for ($t = 0; $t -lt 120; $t++) {
        Start-Sleep -Milliseconds 500
        $cur = 0; try { $cur = $doc.InlineShapes.Count } catch {}
        if ($before -eq 0 -or $cur -lt $before) { Start-Sleep -Milliseconds 1500; break }
    }
    $after = $doc.InlineShapes.Count
    $doc.SaveAs2($Dst, 16)
    Write-Output ("OK:" + $before + "->" + $after)
} finally {
    if ($null -ne $doc) { try { $doc.Close($false) } catch {} }
    if ($null -ne $word) { try { $word.Quit() } catch {} }
}
"""


def available() -> bool:
    return os.name == "nt"


def convert_mathtype(docx: str, mode: str = "convert", show_word: bool = False, out: str | None = None,
                     timeout: int = 240) -> tuple[bool, str, str]:
    """Trả về (thành công, đường dẫn file đã chuyển hoặc thông báo lỗi, ghi chú)."""
    if os.name != "nt":
        return False, "", "Đổi MathType qua Word chỉ chạy trên Windows có Word và MathType."
    d = tempfile.mkdtemp(prefix="nhd_word_")
    src = os.path.join(d, "goc.docx")
    dst = out or os.path.join(d, "da_chuyen.docx")
    shutil.copyfile(docx, src)                         # luôn làm trên bản sao
    script = os.path.join(d, "mt.ps1")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(PS)
    ps = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    keys = "%\\" if mode == "toggle_tex" else ""
    try:
        r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, src, dst,
                            "1" if show_word else "0", ";".join(MACROS.get(mode, [])), keys],
                           capture_output=True, timeout=timeout, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError) as e:
        return False, "", str(e)
    out_s = r.stdout.decode("utf-8", "replace").strip()
    err_s = r.stderr.decode("utf-8", "replace").strip()
    if r.returncode == 0 and out_s.startswith("OK:") and os.path.exists(dst):
        return True, dst, out_s
    return False, "", err_s or out_s or "Word không chạy được lệnh MathType"
