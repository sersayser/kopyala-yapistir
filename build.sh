#!/usr/bin/env bash
# macOS / Linux için tek dosyalık binary üretir.
# Sonuç: dist/secili-metin-kaydedici  (+ Mac'te dist/Calistir.command)
#
# Kullanım:
#     ./build.sh

set -euo pipefail
cd "$(dirname "$0")"

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "PyInstaller bulunamadı. Kurmak için: pip install pyinstaller"
    exit 1
fi

rm -rf build dist *.spec

echo "==> PyInstaller ile build alınıyor..."
pyinstaller \
    --onefile \
    --name secili-metin-kaydedici \
    --console \
    --noconfirm \
    --clean \
    app.py

BIN="dist/secili-metin-kaydedici"
if [[ ! -x "$BIN" ]]; then
    echo "HATA: $BIN üretilmedi."
    exit 1
fi

echo ""
echo "==> Çıktı: $BIN ($(du -h "$BIN" | cut -f1))"

# macOS: çift tıkla çalıştırılabilir bir .command wrapper oluştur
if [[ "$(uname)" == "Darwin" ]]; then
    WRAPPER="dist/Calistir.command"
    cat > "$WRAPPER" <<'WRAPEOF'
#!/bin/bash
# Bu dosyayı çift tıklayarak Terminal'de çalıştırın.
cd "$(dirname "$0")"
./secili-metin-kaydedici
echo ""
echo "(çıkmak için bu pencereyi kapatabilirsiniz)"
read -n 1 -s -r -p "Devam etmek için bir tuşa basın..."
WRAPEOF
    chmod +x "$WRAPPER"
    echo "==> Mac wrapper: $WRAPPER (Finder'da çift tıkla)"
fi

# build/ ve .spec artık gereksiz — sadece dist/ kalsın
rm -rf build *.spec

echo ""
echo "Tamam. Binary'yi şöyle çalıştırabilirsiniz:"
echo "    $BIN"
echo "    $BIN --help"
echo "    $BIN --record-hotkey"
echo "    $BIN --append --timestamp"
