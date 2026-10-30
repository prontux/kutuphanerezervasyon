import os
import time
from datetime import datetime
import cv2
import pytesseract
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("Basliyor - Bulut Uyumlu Mod (Ön Hazırlık: 19:00, Rezervasyon: 13:00)")

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--start-maximized")
opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=opts)

try:
    driver.get("https://ktprezervasyon.uskudar.bel.tr/?p=2")
    time.sleep(3)
    w = WebDriverWait(driver, 20)
    
    try:
        el_read = w.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'okudum')]")))
        driver.execute_script("arguments[0].click();", el_read)
    except:
        pass
    
    time.sleep(1)
    u = w.until(EC.presence_of_element_located((By.NAME, "kullanici")))
    u.clear()
    u.send_keys(os.environ.get('TC_KIMLIK'))
    
    p = driver.find_element(By.NAME, "sifre")
    p.clear()
    p.send_keys(os.environ.get('SIFRE'))

    img = w.until(EC.presence_of_element_located((By.XPATH, "//img[@class='captcha']")))
    
    img_path = "c.png"
    th_path = "ct.png"
    
    code = ""
    deneme = 0
    while deneme < 10:
        try:
            img.screenshot(img_path)
            icv = cv2.imread(img_path)
            if icv is None:
                time.sleep(0.5)
                deneme += 1
                continue
            gray = cv2.cvtColor(icv, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, th = cv2.threshold(resized, 140, 255, cv2.THRESH_BINARY)
            cv2.imwrite(th_path, th)
            
            cfg = '--psm 8 -c tessedit_char_whitelist=0123456789'
            code = pytesseract.image_to_string(Image.open(th_path), config=cfg).strip()
            
            if len(code) == 6 and code.isdigit():
                print("Captcha Başarıyla Okundu:", code)
                break
        except Exception:
            pass
        deneme += 1
        time.sleep(0.1)
    
    cinp = driver.find_element(By.NAME, "code_girisForm")
    cinp.send_keys(code)
    
    lbtn = w.until(EC.presence_of_element_located((By.XPATH, "//button[@type='submit']")))
    driver.execute_script("arguments[0].click();", lbtn)
    print("Giris yapildi")
    time.sleep(2)

    rmenu = w.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Rezervasyon')]")))
    driver.execute_script("arguments[0].click();", rmenu)

    kbtn = w.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'HALUK DURSUN KÜTÜPHANESİ')]")))
    driver.execute_script("arguments[0].click();", kbtn)

    # 1. ADIM (Ön Hazırlık): İlk ekranda 19:00 seçilerek içeri giriliyor
    print("Ön hazırlık için 19:00 seansına tıklanıyor...")
    s1 = w.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@data-seans, '19:00')]")))
    driver.execute_script("arguments[0].click();", s1)

    print("Gece yarısı 00:00 bekleniyor...")
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute >= 0:
            print("Saat 00:00 oldu, işlem başlatılıyor!")
            break
        time.sleep(0.01)

    print("Sayfa yenileniyor...")
    driver.refresh()
    
    w.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    print("Filtre açılıyor")
    fbtn = w.until(EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'acKapat')]")))
    driver.execute_script("arguments[0].click();", fbtn)

    print("En son tarih seçiliyor")
    driver.execute_script("var ts = document.querySelector('select[name=\"tarih\"]'); if(ts){ ts.selectedIndex = ts.options.length - 1; ts.dispatchEvent(new Event('change')); if(window.jQuery){ jQuery(ts).trigger('change'); }}")
    time.sleep(0.8)

    # 2. ADIM (00:00 Sonrası): Asıl rezervasyon için 13:00 seçiliyor
    print("Asıl rezervasyon için 13:00 seansı seçiliyor...")
    driver.execute_script("var ss = document.querySelector('select[name=\"seans\"]'); if(ss){ for(var i=0; i<ss.options.length; i++){ if(ss.options[i].text.includes('13:00')){ ss.selectedIndex = i; break; }} if(ss.selectedIndex <= 0 && ss.options.length > 1){ ss.selectedIndex = 1; } ss.dispatchEvent(new Event('change')); if(window.jQuery){ jQuery(ss).trigger('change'); }}")
    
    print("Seansın yüklenmesi bekleniyor...")
    time.sleep(1.5)

    print("Koltuk seçiliyor (69-9)")
    seat_js = """
        var seat = document.querySelector("span[data-id='69-9']");
        if(seat){
            seat.scrollIntoView({block: 'center', inline: 'center'});
            var rect = seat.getBoundingClientRect();
            var cx = rect.left + (rect.width / 2);
            var cy = rect.top + (rect.height / 2);
            ['mousedown', 'mouseup', 'click'].forEach(function(eType) {
                var ev = new MouseEvent(eType, { view: window, bubbles: true, cancelable: true, clientX: cx, clientY: cy });
                seat.dispatchEvent(ev);
            });
            if (window.jQuery) { jQuery("span[data-id='69-9']").trigger('click'); }
        }
    """
    driver.execute_script(seat_js)

    print("EVET butonuna basılıyor...")
    btn_js = """
        var btn = document.querySelector('button.btn.btn-success.evet') || document.querySelector('button.evet');
        if(btn){
            btn.scrollIntoView({block: 'center', inline: 'center'});
            ['mousedown', 'mouseup', 'click'].forEach(function(eType) {
                var ev = new MouseEvent(eType, { view: window, bubbles: true, cancelable: true });
                btn.dispatchEvent(ev);
            });
            btn.click();
        }
    """
    driver.execute_script(btn_js)
    
    print("Rezervasyon başarıyla tamamlandı!")
    time.sleep(20)

except Exception as e:
    print("HATA OLUSTU:", str(e))
    time.sleep(30)

finally:
    driver.quit()
