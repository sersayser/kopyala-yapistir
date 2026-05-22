#!/usr/bin/env python3
"""Erişilebilirlik izni GEREKTİRMEYEN Chrome veri-yolu testi.

Strateji:
  - Chrome'un kendi AppleScript executeJavaScript arayüzü kullanılır
    (System Events / klavye simülasyonu YOK).
  - Sayfada seçim yapılır ve document.execCommand("copy") ile panoya
    yazılır.
  - Python pyperclip ile panoyu okur ve rapor-N.txt'ye yazar.

Bu test, kullanıcı gerçekten Cmd+Shift+S'ye bastığında app.py'nin
yapacağı işin "Chrome -> pano -> dosya" kısmının çalıştığını doğrular.
Klavye simülasyonu kısmı (pynput) ayrı bir izne tabidir; o, kullanıcı
Erişilebilirlik iznini verdikten sonra çalışır.
"""
import html
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app import next_filename  # noqa: E402
import pyperclip  # noqa: E402

TEST_TEXT = (
    "Rapor — Şişli\n"
    "Müvekkil: Ahmet Çelik\n"
    "Tarih: 22.05.2026\n"
    "Tutar: 12.345,67 ₺\n"
    "Notlar: «alıntı», em — dash, % işareti, € €"
)


def osa(script: str) -> tuple[int, str, str]:
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, check=False,
    )
    return r.returncode, r.stdout, r.stderr


def main() -> int:
    out_dir = Path.cwd() / "raporlar"
    # Önceki test dosyalarını temizleyelim ki sayım baştan başlasın
    if out_dir.exists():
        for p in out_dir.glob("rapor-*.txt"):
            p.unlink()

    tmpdir = Path(tempfile.mkdtemp(prefix="smk-clip-"))
    html_path = tmpdir / "test.html"
    safe_text = html.escape(TEST_TEXT)
    html_path.write_text(
        "<!DOCTYPE html>\n"
        "<html lang='tr'><head><meta charset='utf-8'></head>\n"
        "<body style='font-family:sans-serif;padding:40px;font-size:20px'>\n"
        f"<pre id='x'>{safe_text}</pre>\n"
        "</body></html>\n",
        encoding="utf-8",
    )
    file_url = f"file://{html_path}"

    # Önceki pano içeriğini yedekle (geri yükleme testi için)
    pre_clip = "PRE_TEST_CLIPBOARD_" + str(int(time.time()))
    pyperclip.copy(pre_clip)
    time.sleep(0.1)
    print(f"[setup] Pano başlangıç değeri: {pre_clip!r}")

    print(f"[1] Chrome'da yeni pencere açılıyor: {file_url}")
    rc, _, err = osa(f'''
tell application "Google Chrome"
  activate
  set newWin to make new window
  set URL of active tab of newWin to "{file_url}"
end tell
''')
    if rc != 0:
        print(f"  [HATA] Pencere açılamadı: {err}", file=sys.stderr)
        return 1
    time.sleep(2.0)

    print("[2] Sayfada metin seçiliyor ve execCommand('copy') ile panoya yazılıyor...")
    js = (
        "var el = document.getElementById('x');"
        "var r = document.createRange(); r.selectNodeContents(el);"
        "var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);"
        "var ok = document.execCommand('copy');"
        "'ok=' + ok + ';sel=' + (s.toString().length) + ' chars'"
    )
    js_escaped = js.replace('\\', '\\\\').replace('"', '\\"')
    rc, stdout, err = osa(f'''
tell application "Google Chrome"
  tell active tab of front window
    execute javascript "{js_escaped}"
  end tell
end tell
''')
    print(f"  Chrome JS sonucu: {stdout.strip() or err.strip()}")
    time.sleep(0.3)

    print("[3] pyperclip ile pano okunuyor...")
    captured = pyperclip.paste()
    print(f"  Pano içeriği ({len(captured)} char): {captured[:80]!r}{'...' if len(captured) > 80 else ''}")

    print("[4] rapor-1.txt dosyasına yazılıyor...")
    target = next_filename(out_dir)
    target.write_text(captured, encoding="utf-8")
    print(f"  Yazıldı: {target}")

    print("[5] Test penceresi kapatılıyor...")
    osa('''
tell application "Google Chrome"
  set winList to every window
  repeat with w in winList
    try
      if URL of active tab of w contains "smk-clip" then
        close w
      end if
    end try
  end repeat
end tell
''')

    try:
        html_path.unlink()
        tmpdir.rmdir()
    except OSError:
        pass

    print()
    print("=" * 64)
    file_content = target.read_text(encoding="utf-8")
    matches = (file_content == TEST_TEXT)
    print(f"Beklenen metin ({len(TEST_TEXT)} char):")
    print("  " + TEST_TEXT.replace("\n", "\\n"))
    print(f"Dosyadaki metin ({len(file_content)} char):")
    print("  " + file_content.replace("\n", "\\n"))
    print("=" * 64)
    if matches:
        print("SONUÇ: GEÇTİ — Chrome -> pano -> dosya zinciri %100 doğru çalıştı.")
        rc = 0
    else:
        print("SONUÇ: BAŞARISIZ — içerik eşleşmedi.")
        rc = 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
