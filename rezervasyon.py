import os
import sys
import time
from datetime import datetime, timedelta
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
LOGIN_DENEME = 30      # giriş için en fazla deneme (zaman sınırı da var)
HAZIRLIK_SON = (23, 55)  # hazırlık (giriş + 19:00) en geç bu saate kadar tekrar denenir
REZ_DENEME = 3         # 00:00 sonrası rezervasyon adımı için deneme sayısı

print(f"Basliyor (Ön Hazırlık: {ON_HAZIRLIK_SEANS}, Rezervasyon: {HEDEF_SEANS}, Koltuk: {KOLTUK})")


def simdi():
    return datetime.now(TZ)


def hazirlik_son_zaman():
    now = simdi()
    if now.hour >= 12:
        return now.replace(hour=HAZIRLIK_SON[0], minute=HAZIRLIK_SON[1], second=0, microsecond=0)
    # Gece yarısından sonra elle test ediliyorsa 5 dakika tanı
    return now + timedelta(minutes=5)


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
    son = hazirlik_son_zaman()
    for n in range(1, LOGIN_DENEME + 1):
        if n > 1 and simdi() >= son:
            print("Giriş için zaman sınırı doldu.")
            break
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

            # Giriş başarılıysa giriş formu kaybolur ve "Rezervasyon" menüsü görünür
            WebDriverWait(driver, 8).until(
                EC.invisibility_of_element_located((By.NAME, "kullanici"))
            )
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
        if now.hour not in (22, 23):
            # 23:00 ile 00:00 dışında bir saatteyse bekleyip saatlerce takılma
            raise RuntimeError(f"Saat {now.strftime('%H:%M')} (TR). Beklenen aralık 22:xx-23:xx. İşlem iptal.")
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


def hazirlik(driver, w, tc, sifre):
    """Giriş + kütüphane + 19:00 seansı. Hata olursa exception fırlatır."""
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


def rezervasyon_yap(driver, w):
    """00:00 sonrası: tarih, seans, koltuk, EVET. Doğrulama sonucunu döner."""
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

    print(f"As
