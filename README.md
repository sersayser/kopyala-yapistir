# Kopyala-Yapıştır

Ekrandaki seçili metni tek tuş kombinasyonuyla `rapor-N.txt` dosyalarına kaydeden çapraz platform terminal uygulaması. Linux / macOS / Windows.

Tarayıcıdan, PDF okuyucudan, editörden — herhangi bir uygulamada metin seçin, ayarladığınız tuş kombinasyonuna basın, metin otomatik olarak `raporlar/` klasörüne yazılır.

## Özellikler

- **Global hotkey** — Hangi uygulamada olursanız olun çalışır
- **İki kayıt kipi**
  - Çoklu dosya: her kopya yeni `rapor-1.txt`, `rapor-2.txt`, ... şeklinde artarak
  - Tek dosya (ekleme): tüm kopyalar aynı `rapor-1.txt` içine boş satırla ayrılarak
- **Opsiyonel zaman damgası** — her kayda `--- YYYY-MM-DD HH:MM:SS ---` başlığı
- **Etkileşimli tuş kaydı** — `--record-hotkey` ile basarak kombinasyon belirleme
- **Önceki pano içeriği korunuyor** — yedekle/geri yükle ile şifreniz / kopyaladığınız önceki şey kaybolmaz
- **Chrome-güvenli** — DevTools kazasını önlemek için modifier release bekleme; gecikmeli pano yazımları için sentinel polling
- **Self-test** — bağımlılıkları, panoyu, izinleri doğrulayan tanı modu

## Kurulum

### Seçenek 1: pip ile (en kolay)

```bash
# Doğrudan GitHub'dan
pip install git+https://github.com/sersayser/kopyala-yapistir.git

# Sonra her yerden çalıştır:
kopyala-yapistir
```

Yerel bir klon üzerinde geliştirme yapıyorsanız:

```bash
git clone https://github.com/sersayser/kopyala-yapistir.git
cd kopyala-yapistir
pip install -e .   # editable install
```

### Seçenek 2: GitHub Releases'tan hazır binary

Her tag push'unda CI otomatik olarak 4 platform için binary üretir. `Releases` sayfasından kendi platformunuza ait zip'i indirin: <https://github.com/sersayser/kopyala-yapistir/releases>

Mevcut platformlar:
- `kopyala-yapistir-macos-arm64.zip` — Apple Silicon Mac (M1/M2/M3/M4)
- `kopyala-yapistir-macos-x86_64.zip` — Intel Mac
- `kopyala-yapistir-linux-x86_64.zip` — Linux x86_64
- `kopyala-yapistir-windows-x86_64.zip` — Windows x86_64

### Seçenek 3: Kaynak + manuel çalıştırma (pip kurmadan)

```bash
git clone https://github.com/sersayser/kopyala-yapistir.git
cd kopyala-yapistir
pip install -r requirements.txt
python3 app.py
```

### Seçenek 4: Kendi platformunuz için binary üret

```bash
git clone https://github.com/sersayser/kopyala-yapistir.git
cd kopyala-yapistir
pip install -r requirements.txt pyinstaller
./build.sh        # macOS / Linux
./dist/secili-metin-kaydedici
```

macOS'ta `dist/Calistir.command`'a çift tıklayarak da başlatabilirsiniz.

## macOS Erişilebilirlik İzni (ZORUNLU)

macOS'ta global tuş dinleme için Erişilebilirlik izni şarttır. Aksi halde uygulama çalışmaz.

1. **Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik**
2. **+** butonuna basın, çalıştırdığınız şeye göre şu yolu ekleyin:
   - Kaynaktan çalıştırıyorsanız: `/usr/bin/python3` ya da `/opt/anaconda3/bin/python3` (sisteminizdeki Python yolu)
   - Binary'den çalıştırıyorsanız: `.../kopyala-yapistir/dist/secili-metin-kaydedici`
3. Yanındaki anahtarı **AÇIK** konuma getirin
4. Uygulamayı kapatıp yeniden başlatın

Hangi yolu eklemeniz gerektiğini `--self-test` veya `--record-hotkey` size söyler.

## Kullanım

### Tuş kombinasyonunu ayarla (bir kez)

```bash
# Etkileşimli — bir kombinasyona basın, otomatik yakalanır
python3 app.py --record-hotkey

# Manuel — string olarak ayarla
python3 app.py --set-hotkey '<ctrl>+<shift>+s'
```

Varsayılan: `<ctrl>+<shift>+s`. Ayar `~/.secili_metin_kaydedici.json` içinde saklanır.

### Çalıştır

```bash
python3 app.py
```

Banner görüntülenir, hotkey dinlenmeye başlar. Metin seçin → hotkey'e basın → `raporlar/rapor-N.txt` oluşur.

### Kayıt kipini değiştir

```bash
# Tek dosya kipi (tüm kopyalar rapor-1.txt'ye eklenir)
python3 app.py --append

# Her kopya zaman damgası alsın
python3 app.py --timestamp

# Çoklu dosya kipine geri dön
python3 app.py --no-append

# Tek seferde her şey
python3 app.py --set-hotkey '<ctrl>+<alt>+r' --append --timestamp
```

## CLI Referansı

```
--set-hotkey KOMBO     Tuş kombinasyonunu string olarak ayarla (kalıcı)
--record-hotkey        Etkileşimli kayıt (Esc=iptal)
--output-dir, -o DIZIN Çıktı dizini (varsayılan: ./raporlar)
--append, --no-append  Tek dosya kipi / çoklu dosya kipi (kalıcı)
--timestamp, --no-timestamp  Zaman damgası başlığı (kalıcı)
--show-config          Mevcut ayarları göster
--self-test            Bağımlılıkları ve izinleri sına
--help, -h             Yardım metni
```

## Örnek Çıktı

### Çoklu dosya kipi (varsayılan)

```
raporlar/
├── rapor-1.txt      ← ilk kopyalama
├── rapor-2.txt      ← ikinci kopyalama
├── rapor-3.txt      ← ...
```

### Ekleme kipi + zaman damgası (`--append --timestamp`)

```
raporlar/rapor-1.txt:

--- 2026-05-22 14:32:15 ---
Müvekkilin ifadesi başlangıcı...

--- 2026-05-22 14:35:48 ---
Tanık beyanı.
İki satırlı.

--- 2026-05-22 14:41:02 ---
Sonuç.
```

## Platform Notları

| Platform | Ek Gereksinim |
|---|---|
| macOS | Erişilebilirlik izni (zorunlu) |
| Linux | X11 önerilir; Wayland'de global hotkey sınırlı çalışabilir. Pano için `xclip` veya `xsel` gerekli. |
| Windows | Ek ayar gerekmez |

## Chrome'da Güvenli Çalışma

Uygulama Chrome ile aşağıdaki önlemleri içerir:

- **DevTools kazası yok**: Kullanıcı `Ctrl+Shift+S` tutarken biz `Cmd+C` simüle edersek OS bunu `Cmd+Shift+C` (DevTools) olarak görür. Bu yüzden modifier release beklenir.
- **Gecikmeli pano yazımı yakalanır**: Sabit `sleep` yerine sentinel + 1.5s polling.
- **Pano restore**: İşlem sonrası kullanıcının önceki pano içeriği geri yüklenir.

## Geliştirici Notları

Birim testleri ve Chrome E2E testleri için:

```bash
# Edge case birim testleri inline olarak app.py içinde değil — manuel koşulur
python3 -c "import app; print(app.timestamp_header())"

# Chrome veri yolu testi (izin gerektirmez)
python3 test_chrome_clipboard.py

# Chrome E2E testi (Erişilebilirlik izni gerektirir)
python3 test_chrome_e2e.py
```

## Lisans

MIT — bkz. [LICENSE](LICENSE)
