import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
import pytesseract
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://ktprezervasyon.uskudar.bel.tr/?p=2"
TZ = ZoneInfo("Europe/Istanbul")
HEDEF_SEANS = "13:00"
ON_HAZIRLIK_SEANS = "19:00"
KOLTUK = "69-9"
YEDEK_INDEX = 2  # 13:00 bulunamazsa listedeki 3. seçenek (index 0 = 1. seçenek)
LOGIN_DENEME = 5

print(f"Basliyor (Ön Hazırlık: {ON_HAZIRLIK_SEANS}, Rezervasyon: {HEDEF_SEANS}, Koltuk: {KOLTUK})")


def simdi():
    return datetime.now(TZ)


def tc_sifre_al():
    tc = os.environ.get("TC_KIMLIK")
    sifre = os.environ.get("SIFRE")
    if not tc or not sifre:
        raise RuntimeError("TC_KIMLIK veya SIFRE ortam değişkeni boş (GitHub Secrets'ı kontrol et).")
    return tc, sifre


def captcha_oku(img, deneme_sayisi=10):
    img_path, th_path = "c.png", "ct.png"
    for _ in range(deneme_sayisi):
        try:
            img.screenshot(img_path)
            icv = cv2.imread(img_path)
            if icv is None:
                time.sleep(0.5)
                continue
            gray = cv2.cvtColor(icv, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, th = cv2.threshold(resized, 140, 255, cv2.THRESH_BINARY)
            cv2.imwrite(th_path, th)
            cfg = "--psm 8 -c tessedit_char_whitelist=0123456789"
            code = pytesseract.image_to_string(Image.open(th_path), config=cfg).strip()
            if len(code) == 6 and code.isdigit():
                return code
        except Exception:
            pass
        time.sleep(0.1)
    return None


def giris_yap(driver, tc, sifre):
    """Captcha yanlış okunursa sayfayı yenileyip tekrar dener. Başarılıysa True döner."""
    for n in range(1, LOGIN_DENEME + 1):
        print(f"Giriş denemesi {n}/{LOGIN_DENEME}")
        try:
            driver.get(URL)
            time.sleep(3)
            w = WebDriverWait(driver, 20)

            try:
                el_read = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'okudum')]"))
                )
                driver.execute_script("arguments[0].click();", el_read)
            except Exception:
                pass

            time.sleep(1)
            u = w.until(EC.presence_of_element_located((By.NAME, "kullanici")))
            u.clear()
            u.send_keys(tc)
            p = driver.find_element(By.NAME, "sifre")
            p.clear()
            p.send_keys(sifre)

            img = w.until(EC.presence_of_element_located((By.XPATH, "//img[@class='captcha']")))
            code = captcha_oku(img)
            if not code:
                print("Captcha okunamadı, yeniden deneniyor.")
                continue
            print("Captcha okundu:", code)

            driver.find_element(By.NAME, "code_girisForm").send_keys(code)
            lbtn = w.until(EC.presence_of_element_located((By.XPATH, "//button[@type='submit']")))
            driver.execute_script("arguments[0].click();", lbtn)

            # Giriş başarılıysa "Rezervasyon" menüsü görünür
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Rezervasyon')]"))
            )
            print("Giriş yapıldı")
            return True
        except Exception as e:
            print("Giriş başarısız:", str(e).splitlines()[0] if str(e) else type(e).__name__)
    return False


def gece_yarisi_bekle():
    print("Gece yarısı 00:00 (Türkiye saati) bekleniyor...")
    while True:
        now = simdi()
        if now.hour == 0:
            print("Saat 00:00 oldu, işlem başlatılıyor!", now.strftime("%H:%M:%S.%f"))
            return
        if now.hour not in (23,):
            # 23:00 ile 00:00 dışında bir saatteyse bekleyip saatlerce takılma
            raise RuntimeError(f"Saat {now.strftime('%H:%M')} (TR). Beklenen aralık 23:xx. İşlem iptal.")
        time.sleep(0.01)


def sonucu_dogrula(driver):
    driver.save_screenshot("sonuc.png")
    try:
        metin = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        metin = ""
    kucuk = metin.lower()
    print("---- Sayfa metni (ilk 500 karakter) ----")
    print(metin[:500])
    print("----------------------------------------")

    hata = ["dolu", "hata", "yapılamaz", "yapilamaz", "başarısız", "basarisiz", "mevcut değil"]
    basari = ["başarı", "basari", "rezervasyonunuz", "tamamlandı", "tamamlandi", "alındı", "alindi"]
    if any(k in kucuk for k in hata):
        return False
    return any(k in kucuk for k in basari)


def main():
    tc, sifre = tc_sifre_al()

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=opts)
    w = WebDriverWait(driver, 20)

    basarili = False
    try:
        if not giris_yap(driver, tc, sifre):
            raise RuntimeError("Giriş yapılamadı (captcha/şifre).")

        rmenu = w.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Rezervasyon')]")))
        driver.execute_script("arguments[0].click();", rmenu)

        kbtn = w.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'HALUK DURSUN KÜTÜPHANESİ')]"))
        )
        driver.execute_script("arguments[0].click();", kbtn)

        print(f"Ön hazırlık için {ON_HAZIRLIK_SEANS} seansına tıklanıyor...")
        s1 = w.until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(@data-seans, '{ON_HAZIRLIK_SEANS}')]"))
        )
        driver.execute_script("arguments[0].click();", s1)

        gece_yarisi_bekle()

        print("Sayfa yenileniyor...")
        driver.refresh()
        w.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        print("Filtre açılıyor")
        fbtn = w.until(EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'acKapat')]")))
        driver.execute_script("arguments[0].click();", fbtn)

        print("En son tarih seçiliyor")
        driver.execute_script(
            "var ts = document.querySelector('select[name=\"tarih\"]');"
            "if(ts){ ts.selectedIndex = ts.options.length - 1;"
            "ts.dispatchEvent(new Event('change'));"
            "if(window.jQuery){ jQuery(ts).trigger('change'); }}"
        )
        time.sleep(0.8)

        print(f"Asıl rezervasyon için {HEDEF_SEANS} seansı seçiliyor...")
        seans_js = """
            var hedef = arguments[0];
            var ss = document.querySelector('select[name="seans"]');
            if(!ss){ return 'select-yok'; }
            for(var i=0; i<ss.options.length; i++){
                if(ss.options[i].text.includes(hedef) || ss.options[i].value.includes(hedef)){
                    ss.selectedIndex = i;
                    ss.dispatchEvent(new Event('change'));
                    if(window.jQuery){ jQuery(ss).trigger('change'); }
                    return 'ok';
                }
            }
            if(ss.options.length > arguments[1]){
                ss.selectedIndex = arguments[1];
                ss.dispatchEvent(new Event('change'));
                if(window.jQuery){ jQuery(ss).trigger('change'); }
                return 'yedek:' + ss.options[arguments[1]].text;
            }
            return 'bulunamadi';
        """
        sonuc = driver.execute_script(seans_js, HEDEF_SEANS, YEDEK_INDEX)
        if sonuc.startswith("yedek:"):
            print(f"UYARI: {HEDEF_SEANS} bulunamadı, listedeki 3. seçenek seçildi -> {sonuc[6:]}")
        elif sonuc != "ok":
            raise RuntimeError(f"Seans seçilemedi ({sonuc}).")

        print("Seansın yüklenmesi bekleniyor...")
        time.sleep(1.5)

        print(f"Koltuk seçiliyor ({KOLTUK})")
        seat_js = """
            var seat = document.querySelector("span[data-id='" + arguments[0] + "']");
            if(!seat){ return 'koltuk-yok'; }
            seat.scrollIntoView({block: 'center', inline: 'center'});
            var rect = seat.getBoundingClientRect();
            var cx = rect.left + (rect.width / 2);
            var cy = rect.top + (rect.height / 2);
            ['mousedown', 'mouseup', 'click'].forEach(function(eType) {
                var ev = new MouseEvent(eType, { view: window, bubbles: true, cancelable: true, clientX: cx, clientY: cy });
                seat.dispatchEvent(ev);
            });
            return 'ok:' + seat.className;
        """
        sonuc = driver.execute_script(seat_js, KOLTUK)
        print("Koltuk sonucu:", sonuc)
        if sonuc == "koltuk-yok":
            raise RuntimeError(f"Koltuk {KOLTUK} sayfada bulunamadı.")

        print("EVET butonu bekleniyor...")
        btn = w.until(
            lambda d: d.find_element(By.CSS_SELECTOR, "button.evet")
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn)
        time.sleep(2)

        basarili = sonucu_dogrula(driver)
        if basarili:
            print("Rezervasyon başarıyla tamamlandı!")
        else:
            print("UYARI: Rezervasyonun başarılı olduğu doğrulanamadı. sonuc.png ve yukarıdaki sayfa metnini kontrol et.")
        time.sleep(5)

    except Exception as e:
        print("HATA OLUSTU:", str(e))
        try:
            driver.save_screenshot("hata.png")
        except Exception:
            pass
    finally:
        driver.quit()

    sys.exit(0 if basarili else 1)


if __name__ == "__main__":
    main()
