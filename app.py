#!/usr/bin/env python3
"""Seçili metni rapor-N.txt dosyalarına kaydeden terminal uygulaması.

Linux / macOS / Windows uyumlu. Global bir tuş kombinasyonu dinler;
basıldığında o anda seçili olan metni (sistem panosu üzerinden) bir
sonraki rapor-N.txt dosyasına yazar.
"""

import argparse
import datetime
import json
import platform
import sys
import threading
import time
from pathlib import Path

try:
    from pynput import keyboard
    from pynput.keyboard import Controller, Key
    import pyperclip
except ImportError:
    print("Gerekli paketler yüklü değil.")
    print()
    print("Yüklemek için:")
    print("    pip install -r requirements.txt")
    print("ya da:")
    print("    pip install pynput pyperclip")
    sys.exit(1)


CONFIG_FILE = Path.home() / ".secili_metin_kaydedici.json"
DEFAULT_HOTKEY = "<ctrl>+<shift>+s"
SENTINEL = "\x00\x01__SMK_SENTINEL_DO_NOT_USE__\x01\x00"


def macos_accessibility_status() -> bool | None:
    """macOS'ta Erişilebilirlik izninin verilip verilmediğini döner.

    True  : izin var
    False : izin yok
    None  : kontrol edilemedi (mac değil veya pyobjc eksik)
    """
    if platform.system() != "Darwin":
        return None
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return None

MODIFIER_KEYS = {
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.shift, Key.shift_l, Key.shift_r,
    Key.alt, Key.alt_l, Key.alt_r,
    Key.cmd, Key.cmd_l, Key.cmd_r,
}
_alt_gr = getattr(Key, "alt_gr", None)
if _alt_gr is not None:
    MODIFIER_KEYS.add(_alt_gr)


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_filename(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    i = 1
    while True:
        candidate = output_dir / f"rapor-{i}.txt"
        if not candidate.exists():
            return candidate
        i += 1


def record_hotkey_interactive() -> str | None:
    """Kullanıcının bastığı tuş kombinasyonunu yakalayıp pynput formatında döner.

    Esc ile iptal. Sadece modifier basılıp non-modifier eksikse reddeder.
    macOS'ta Erişilebilirlik izni gerekir; yoksa peşinen uyarı verir.
    """
    if platform.system() == "Darwin" and macos_accessibility_status() is False:
        print()
        print("[HATA] macOS Erişilebilirlik izni yok — tuş dinlenemez.")
        print("       Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik")
        print(f"       altında şu yola izin verin: {sys.executable}")
        return None

    print()
    print("=" * 64)
    print(" Tuş Kombinasyonu Kaydı")
    print("=" * 64)
    print(" Kullanmak istediğiniz tuş kombinasyonunu birlikte tuşlayın.")
    print(" Örnek: Ctrl + Shift + S")
    print(" İptal: Esc")
    print()
    print(" Bekleniyor...", flush=True)

    pressed_order: list[str] = []
    pressed_set: set[str] = set()
    has_non_modifier = {"v": False}
    cancelled = {"v": False}
    done = threading.Event()

    def to_token(key):
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            return "<ctrl>", True
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            return "<shift>", True
        if key in (Key.alt, Key.alt_l, Key.alt_r):
            return "<alt>", True
        if key in (Key.cmd, Key.cmd_l, Key.cmd_r):
            return "<cmd>", True
        if _alt_gr is not None and key == _alt_gr:
            return "<alt_gr>", True
        try:
            ch = getattr(key, "char", None)
            if ch:
                return ch.lower(), False
        except AttributeError:
            pass
        name = getattr(key, "name", None)
        if name:
            return f"<{name}>", False
        return None, False

    def on_press(key):
        if key == Key.esc:
            cancelled["v"] = True
            done.set()
            return False
        token, is_mod = to_token(key)
        if not token:
            return
        if token not in pressed_set:
            pressed_set.add(token)
            pressed_order.append(token)
            if not is_mod:
                has_non_modifier["v"] = True

    def on_release(_key):
        if has_non_modifier["v"]:
            done.set()
            return False

    with keyboard.Listener(on_press=on_press, on_release=on_release):
        done.wait()

    if cancelled["v"]:
        print(" İptal edildi.")
        return None
    if not has_non_modifier["v"]:
        print(" [UYARI] Karakter tuşu basılmadı; geçersiz kombinasyon.")
        return None

    order_map = {"<ctrl>": 0, "<alt>": 1, "<shift>": 2, "<cmd>": 3, "<alt_gr>": 4}
    mods = sorted(
        (t for t in pressed_order if t in order_map),
        key=lambda t: order_map[t],
    )
    rest = [t for t in pressed_order if t not in order_map]
    combo = "+".join(mods + rest)
    print(f" Yakalandı: {combo}")
    return combo


def wait_for_hotkey_release(timeout: float = 0.4) -> None:
    """Kullanıcı tuş kombinasyonunu bırakana dek kısa bir süre bekler.

    Kritik: biz Cmd/Ctrl+C simüle ederken kullanıcı hâlâ Shift'i tutuyorsa
    sistem bunu Cmd+Shift+C olarak görür ve Chrome'da DevTools'un açılması
    gibi yan etkiler oluşur. İlk tuş bırakma anına kadar bekliyoruz.
    """
    released = threading.Event()

    def on_release(_key):
        released.set()
        return False

    listener = keyboard.Listener(on_release=on_release)
    listener.start()
    released.wait(timeout=timeout)
    if listener.running:
        listener.stop()
    time.sleep(0.05)


def capture_selection(timeout: float = 1.5) -> str:
    """Platforma uygun kopyalama tuşunu simüle eder ve panodan metni okur.

    - Önce kullanıcının hotkey'i bırakmasını bekler (Chrome'da DevTools
      kazasını önlemek için).
    - Panoya sentinel yazar; sentinel değişene kadar polling yapar.
      Böylece Chrome'un gecikmeli pano yazımları da yakalanır.
    - Sonunda kullanıcının önceki pano içeriğini geri yükler.
    """
    try:
        old_clip = pyperclip.paste()
    except pyperclip.PyperclipException:
        old_clip = None

    wait_for_hotkey_release()

    try:
        pyperclip.copy(SENTINEL)
    except pyperclip.PyperclipException as exc:
        print(f"    [HATA] Panoya yazılamadı: {exc}")
        return ""

    kb = Controller()
    modifier = Key.cmd if platform.system() == "Darwin" else Key.ctrl

    try:
        with kb.pressed(modifier):
            kb.press("c")
            kb.release("c")
    except Exception as exc:
        print(f"    [HATA] Tuş simülasyonu başarısız: {exc}")
        return ""

    text = SENTINEL
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.05)
        try:
            current = pyperclip.paste()
        except pyperclip.PyperclipException:
            continue
        if current is None:
            continue
        if current != SENTINEL:
            text = current
            break

    captured = "" if text == SENTINEL else text

    if old_clip is not None:
        try:
            pyperclip.copy(old_clip)
        except pyperclip.PyperclipException:
            pass

    return captured


APPEND_FILE_NAME = "rapor-1.txt"


def timestamp_header() -> str:
    return datetime.datetime.now().strftime("--- %Y-%m-%d %H:%M:%S ---")


def append_to_single_file(output_dir: Path, text: str, add_timestamp: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / APPEND_FILE_NAME
    existing = path.exists() and path.stat().st_size > 0
    with open(path, "a", encoding="utf-8") as f:
        if existing:
            f.write("\n")
        if add_timestamp:
            f.write(timestamp_header() + "\n")
        f.write(text.rstrip("\n"))
        f.write("\n")
    return path


def write_new_file(output_dir: Path, text: str, add_timestamp: bool) -> Path:
    path = next_filename(output_dir)
    content = text
    if add_timestamp:
        content = timestamp_header() + "\n" + text
    path.write_text(content, encoding="utf-8")
    return path


def make_handler(output_dir: Path, append_mode: bool, add_timestamp: bool):
    counter = {"saved": 0}

    def on_hotkey():
        text = capture_selection()
        if not text.strip():
            print("    [UYARI] Seçili metin yok ya da pano boş geldi.")
            return
        try:
            if append_mode:
                path = append_to_single_file(output_dir, text, add_timestamp)
            else:
                path = write_new_file(output_dir, text, add_timestamp)
        except OSError as exc:
            print(f"    [HATA] Yazılamadı: {exc}")
            return
        counter["saved"] += 1
        suffix = " (ekleme)" if append_mode else ""
        ts_suffix = " +zaman damgası" if add_timestamp else ""
        print(
            f"    [OK] Kaydedildi -> {path.name}{suffix}{ts_suffix} "
            f"({len(text)} karakter, oturumda {counter['saved']}. kayıt)"
        )

    return on_hotkey


def parse_args():
    parser = argparse.ArgumentParser(
        description="Seçili metni rapor-N.txt dosyasına kaydet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Tuş kombinasyonu örnekleri:\n"
            "    '<ctrl>+<shift>+s'   (tüm platformlar)\n"
            "    '<ctrl>+<alt>+r'\n"
            "    '<cmd>+<shift>+s'    (macOS Command tuşu)\n"
        ),
    )
    parser.add_argument(
        "--set-hotkey",
        metavar="KOMBO",
        help="Tuş kombinasyonunu string olarak kaydet. Bir kez çalıştırın, ayar saklanır.",
    )
    parser.add_argument(
        "--record-hotkey",
        action="store_true",
        help="Etkileşimli kayıt: tuş kombinasyonunu basarak belirleyin (Esc=iptal).",
    )
    parser.add_argument(
        "--output-dir", "-o",
        metavar="DIZIN",
        help="Çıktı dizini. Varsayılan: çalıştırıldığı klasördeki './raporlar'.",
    )
    parser.add_argument(
        "--append",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Tek dosya kipi. --append verilirse tüm kopyalamalar "
            f"'{APPEND_FILE_NAME}' içine boş satırla ayrılarak eklenir. "
            "--no-append çoklu dosya kipine döner. Ayar kalıcıdır."
        ),
    )
    parser.add_argument(
        "--timestamp",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Her kaydın başına '--- YYYY-MM-DD HH:MM:SS ---' satırı ekler. "
            "Hem ekleme hem çoklu dosya kipinde çalışır. Ayar kalıcıdır."
        ),
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Kayıtlı ayarları göster ve çık.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Bağımlılıkları, panoyu ve dosya yazımını sınar; sonra çıkar.",
    )
    return parser.parse_args()


def self_test() -> int:
    """Çalışma ortamını sınar. Chrome testi gerektirmez."""
    print("Self-test başlıyor...")
    ok = True

    # Üst-seviye import zaten yapıldı; eğer eksik olsaydı program buraya
    # ulaşamazdı. Burada sürüm bilgisini göstermeye çalışıyoruz.
    print(" 1) pynput / pyperclip yüklü mü?", end=" ")
    try:
        from importlib.metadata import version as _ver
        print(f"OK (pynput={_ver('pynput')}, pyperclip={_ver('pyperclip')})")
    except Exception:
        print("OK (frozen build — sürüm bilgisi yok ama modüller yüklü)")

    print(" 2) Pano yaz / oku round-trip:", end=" ")
    try:
        original = pyperclip.paste()
    except Exception:
        original = None
    try:
        marker = "SMK-TEST-" + str(int(time.time()))
        pyperclip.copy(marker)
        time.sleep(0.1)
        got = pyperclip.paste()
        if got == marker:
            print("OK")
        else:
            print(f"BAŞARISIZ (yazılan: {marker!r}, okunan: {got!r})")
            ok = False
    except pyperclip.PyperclipException as exc:
        print(f"BAŞARISIZ: {exc}")
        ok = False
    finally:
        if original is not None:
            try:
                pyperclip.copy(original)
            except Exception:
                pass

    print(" 3) Çıktı dizini yazma testi:", end=" ")
    try:
        test_dir = Path.cwd() / "raporlar"
        test_dir.mkdir(parents=True, exist_ok=True)
        probe = test_dir / ".smk_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"OK ({test_dir})")
    except Exception as exc:
        print(f"BAŞARISIZ: {exc}")
        ok = False

    print(" 4) Sonraki dosya adı hesaplaması:", end=" ")
    try:
        nxt = next_filename(Path.cwd() / "raporlar")
        print(f"OK ({nxt.name})")
    except Exception as exc:
        print(f"BAŞARISIZ: {exc}")
        ok = False

    print(" 5) pynput Controller örnek oluşturma:", end=" ")
    try:
        Controller()
        print("OK")
    except Exception as exc:
        print(f"BAŞARISIZ: {exc}")
        ok = False

    print(" 6) Hotkey ayrıştırma (GlobalHotKeys):", end=" ")
    try:
        h = keyboard.GlobalHotKeys({DEFAULT_HOTKEY: lambda: None})
        h_parsed = True
        del h
        print("OK" if h_parsed else "BAŞARISIZ")
    except Exception as exc:
        print(f"BAŞARISIZ: {exc}")
        ok = False

    if platform.system() == "Darwin":
        print(" 7) macOS Erişilebilirlik izni:", end=" ")
        ax = macos_accessibility_status()
        if ax is True:
            print("OK")
        elif ax is False:
            print("YOK (uygulama gerçek kullanımda çalışmaz)")
            print(f"      İzin verilmesi gereken yol: {sys.executable}")
            ok = False
        else:
            print("KONTROL EDİLEMEDİ")

    print()
    print("Sonuç:", "TÜM TESTLER GEÇTİ" if ok else "BAZI TESTLER BAŞARISIZ")
    return 0 if ok else 1


def main():
    args = parse_args()

    if args.self_test:
        sys.exit(self_test())

    config = load_config()

    if args.set_hotkey:
        config["hotkey"] = args.set_hotkey
        save_config(config)
        print(f"Tuş kombinasyonu kaydedildi: {args.set_hotkey}")
        print(f"Ayar dosyası: {CONFIG_FILE}")

    if args.record_hotkey:
        combo = record_hotkey_interactive()
        if combo:
            config["hotkey"] = combo
            save_config(config)
            print(f" Ayar dosyasına yazıldı: {CONFIG_FILE}")
        sys.exit(0 if combo else 1)

    if args.append is not None:
        config["append_mode"] = bool(args.append)
        save_config(config)
        print(
            f"Kayıt kipi güncellendi: "
            f"{'tek dosya (ekleme)' if args.append else 'her kopya yeni dosya'}"
        )

    if args.timestamp is not None:
        config["timestamp"] = bool(args.timestamp)
        save_config(config)
        print(f"Zaman damgası: {'açık' if args.timestamp else 'kapalı'}")

    if args.show_config:
        if config:
            print(json.dumps(config, indent=2, ensure_ascii=False))
        else:
            print("(henüz ayar kaydedilmemiş)")
        return

    hotkey = config.get("hotkey", DEFAULT_HOTKEY)
    append_mode = bool(config.get("append_mode", False))
    add_timestamp = bool(config.get("timestamp", False))
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else Path.cwd() / "raporlar"
    )

    bar = "=" * 64
    print(bar)
    print(" Seçili Metin Kaydedici")
    print(bar)
    print(f" Tuş kombinasyonu : {hotkey}")
    print(f" Çıktı dizini     : {output_dir}")
    if append_mode:
        target = output_dir / APPEND_FILE_NAME
        kb_size = ""
        if target.exists():
            kb_size = f" (mevcut: {target.stat().st_size} bayt)"
        print(f" Kayıt kipi       : TEK DOSYA — {APPEND_FILE_NAME}{kb_size}")
        print("                    Yeni kopyalar boş satırla araya eklenir.")
    else:
        print(" Kayıt kipi       : ÇOKLU DOSYA — her kopya yeni rapor-N.txt")
        print(f" Sonraki dosya    : {next_filename(output_dir).name}")
    print(f" Zaman damgası    : {'AÇIK' if add_timestamp else 'kapalı'}")
    print(f" Platform         : {platform.system()}")
    print("-" * 64)
    print(" Kullanım:")
    print("   1) Herhangi bir uygulamada (Chrome, PDF, editör...) metin seçin")
    print("   2) Yukarıdaki tuş kombinasyonuna basın")
    print("   3) Metin otomatik olarak yeni bir rapor-N.txt dosyasına yazılır")
    print()
    print(" Çıkış: Ctrl+C")
    print(bar)

    if platform.system() == "Darwin":
        ax = macos_accessibility_status()
        if ax is False:
            print()
            print(" " + "!" * 60)
            print(" UYARI: macOS Erişilebilirlik izni YOK.")
            print(" Bu izin olmadan tuş kombinasyonu dinlenemez ve Cmd+C")
            print(" simülasyonu Chrome'a ulaşmaz — uygulama çalışmayacaktır.")
            print()
            print(" Adımlar:")
            print("   1) Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik")
            print("   2) + butonuna basın ve şu dosyayı ekleyin:")
            print(f"        {sys.executable}")
            print("      Alternatif olarak Terminal.app / iTerm uygulamasını ekleyin.")
            print("   3) Eklediğiniz öğenin yanındaki anahtarı AÇIK konuma getirin.")
            print("   4) Bu uygulamayı kapatıp yeniden başlatın.")
            print(" " + "!" * 60)
        elif ax is True:
            print()
            print(" [OK] macOS Erişilebilirlik izni verilmiş.")
        else:
            print()
            print(" Not (macOS): Sistem Ayarları > Gizlilik ve Güvenlik >")
            print(" Erişilebilirlik altında Python ya da Terminal'e izin verilmelidir.")
    elif platform.system() == "Linux":
        print()
        print(" Not (Linux): Wayland oturumlarında global tuş dinleme")
        print(" sınırlı çalışabilir. Sorun yaşarsanız X11 oturumunu deneyin.")
        print(" Pano için 'xclip' veya 'xsel' kurulu olmalıdır.")
    print()

    on_hotkey = make_handler(output_dir, append_mode, add_timestamp)

    try:
        with keyboard.GlobalHotKeys({hotkey: on_hotkey}) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("\nÇıkılıyor...")
    except ValueError as exc:
        print(f"\n[HATA] Geçersiz tuş kombinasyonu '{hotkey}': {exc}")
        print("Doğru format örnekleri:")
        print("    '<ctrl>+<shift>+s'")
        print("    '<ctrl>+<alt>+r'")
        print("    '<cmd>+<shift>+c'   (macOS)")
        print()
        # PyInstaller frozen build'de sys.argv[0] = binary yolu;
        # script modunda 'python app.py'. Kullanıcıya uygun komutu göster.
        is_frozen = getattr(sys, "frozen", False)
        invoke = sys.argv[0] if is_frozen else f"python {Path(__file__).name}"
        print(f"Yeni ayar için: {invoke} --set-hotkey '<ctrl>+<alt>+r'")
        print(f"Etkileşimli için: {invoke} --record-hotkey")
        sys.exit(1)


if __name__ == "__main__":
    main()
