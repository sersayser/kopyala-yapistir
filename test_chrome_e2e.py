#!/usr/bin/env python3
"""Chrome'da capture_selection() uçtan uca testi.

Akış:
  1. Test HTML dosyası oluştur (file://... URL)
  2. Chrome'da YENİ bir pencere aç (mevcut sekmelere dokunmaz)
  3. Sayfa içinde Cmd+A ile metni seç
  4. app.capture_selection() çağır
  5. Yakalanan metin beklenenle eşleşiyor mu kontrol et
  6. Sadece açılan test penceresini kapat

Chrome'a hiçbir DevTools komutu gönderilmiyor; eğer hatalı modifier
yönetimi DevTools açarsa testin sonunda fark ederiz.
"""
import html
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app import capture_selection  # noqa: E402

TEST_TEXT = "BENZERSIZ_CHROME_TEST_METNI_42xyz_Şuşi_ŞŞşşİiĞğÜü"


def osa(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"  [osascript stderr] {result.stderr.strip()}", file=sys.stderr)
    return result.stdout.strip()


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="smk-e2e-"))
    html_path = tmpdir / "test.html"
    safe_text = html.escape(TEST_TEXT)
    html_path.write_text(
        "<!DOCTYPE html>\n"
        "<html lang='tr'><head><meta charset='utf-8'>"
        "<title>SMK E2E Test</title></head>\n"
        "<body style='font-size:28px;padding:60px;font-family:sans-serif'>\n"
        f"<p id='x'>{safe_text}</p>\n"
        "</body></html>\n",
        encoding="utf-8",
    )
    file_url = f"file://{html_path}"

    print(f"1) Test sayfası: {file_url}")
    print("2) Chrome'da yeni pencere açılıyor (mevcut sekmelerine dokunulmuyor)...")
    osa(f'''
tell application "Google Chrome"
  activate
  set newWin to make new window
  set URL of active tab of newWin to "{file_url}"
end tell
''')
    time.sleep(2.0)

    print("3) Sayfada Cmd+A ile metin seçiliyor...")
    osa('''
tell application "Google Chrome" to activate
delay 0.2
tell application "System Events"
  tell process "Google Chrome"
    keystroke "a" using {command down}
  end tell
end tell
''')
    time.sleep(0.5)

    print("4) capture_selection() çağrılıyor...")
    captured = capture_selection()

    print("5) Test penceresi kapatılıyor (Cmd+Shift+W ile pencere)...")
    osa('''
tell application "Google Chrome" to activate
delay 0.1
tell application "System Events"
  tell process "Google Chrome"
    keystroke "w" using {command down, shift down}
  end tell
end tell
''')

    try:
        html_path.unlink()
        tmpdir.rmdir()
    except OSError:
        pass

    print()
    print("=" * 60)
    print(f"Beklenen ({len(TEST_TEXT)} char): {TEST_TEXT!r}")
    print(f"Alınan   ({len(captured)} char): {captured!r}")
    print("=" * 60)

    if TEST_TEXT in captured:
        print("SONUÇ: GEÇTİ — Chrome'dan metin başarıyla yakalandı.")
        return 0
    if not captured:
        print("SONUÇ: BAŞARISIZ — hiç metin alınamadı.")
        print("       Olası neden: Terminal'e Erişilebilirlik izni yok,")
        print("       ya da Chrome'da seçim oluşmadı.")
        return 1
    print("SONUÇ: KISMI — bir şey yakalandı ama beklenenle eşleşmiyor.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
