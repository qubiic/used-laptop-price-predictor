import re
import time
import csv
import threading
from queue import Queue
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

INPUT_FILE = "laptops_raw.csv"
OUTPUT_FILE = "laptops_raw.csv"
NUM_WORKERS = 4

FIELDNAMES = [
    "url", "name", "price_idr", "sold_count", "rating",
    "brand", "cpu", "cpu_full", "ram_gb", "storage_raw",
    "ssd_gb", "storage_type", "nvme", "screen_inch",
    "resolution", "display_type", "touchscreen",
    "gpu", "gpu_type", "os", "battery_hours", "condition", "error",
]

def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

def extract_spec(text, patterns):
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def parse_page(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='lblPDPDetailProductName']")
            )
        )
        for _ in range(8):
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(0.3)
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        def get(testid):
            el = soup.find(attrs={"data-testid": testid})
            return el.text.strip() if el else None

        name = get("lblPDPDetailProductName")
        if not name:
            return {"url": url, "error": "name not found"}

        price_raw = get("lblPDPDetailProductPrice")
        price = int(re.sub(r"[^\d]", "", price_raw)) if price_raw else None

        sold_raw = get("lblPDPDetailProductSoldCounter")
        sold = re.search(r"[\d,]+", sold_raw).group().replace(",", "") if sold_raw else None

        desc_el = soup.find(attrs={"data-testid": "lblPDPDescriptionProduk"})
        text = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

        brand_m = re.search(
            r"\b(Lenovo|Dell|HP|Asus|Acer|MSI|Apple|Samsung|Toshiba|Sony|Fujitsu|Huawei|LG|Razer)\b",
            name, re.IGNORECASE
        )

        ssd_m = extract_spec(text, [
            r"SSD\s*(?:NVME|NVMe|M\.2)?\s*(\d+)\s*(?:GB|TB)",
            r"(\d+)\s*GB\s+SSD", r"(\d+)\s*TB\s+SSD",
        ])

        return {
            "url": url,
            "name": name,
            "price_idr": price,
            "sold_count": sold,
            "rating": get("lblPDPDetailProductRatingNumber"),
            "brand": brand_m.group(1).title() if brand_m else None,
            "cpu": extract_spec(text, [
                r"Intel\s+Core\s+(i\d[\w\-\s]+?)(?:\s+\d+\.\d+\s*GHz|\s*,|\s*\n|RAM|Memory)",
                r"AMD\s+Ryzen\s+([\d\w\s\-]+?)(?:\s+\d+\.\d+\s*GHz|\s*,|\s*\n|RAM|Memory)",
                r"(Intel\s+Core\s+i\d[\w\s\-]+?\d{4}[A-Z0-9]*)",
                r"(AMD\s+Ryzen\s+\d[\w\s]+?\d{4}[A-Z0-9]*)",
                r"(Intel\s+Core\s+[iUH]\d[\w\-]+)",
            ]),
            "cpu_full": extract_spec(text, [
                r"(Intel\s+Core\s+i\d[^\n\r,]{3,40})",
                r"(AMD\s+Ryzen[^\n\r,]{3,40})",
            ]),
            "ram_gb": extract_spec(text, [
                r"RAM[:\s]+(\d+)\s*GB",
                r"Memory[:\s]+(?:DDR\d\s+)?(\d+)\s*GB",
                r"(\d+)\s*GB\s+(?:DDR\d|RAM)",
            ]),
            "storage_raw": extract_spec(text, [
                r"(SSD\s*(?:NVME|NVMe|M\.2)?\s*[\d,\-\/\s]+(?:GB|TB)[^\n\r,]{0,30})",
                r"(HDD\s*[\d,\-\/\s]+(?:GB|TB)[^\n\r,]{0,30})",
            ]),
            "ssd_gb": ssd_m,
            "storage_type": "SSD" if re.search(r"\bSSD\b", text, re.I) else (
                "HDD" if re.search(r"\bHDD\b", text, re.I) else None),
            "nvme": "Yes" if re.search(r"\bNVME\b|\bNVMe\b|\bM\.2\b", text, re.I) else "No",
            "screen_inch": extract_spec(text, [
                r"Layar\s+([\d\.]+)\s*inch",
                r"([\d\.]+)\s*inch",
            ]),
            "resolution": extract_spec(text, [
                r"(\d{3,4}\s*[xX]\s*\d{3,4})",
                r"(Full\s*HD|FHD|HD|QHD|4K)",
            ]),
            "display_type": "IPS" if re.search(r"\bIPS\b", text, re.I) else None,
            "touchscreen": "Yes" if re.search(r"touch\s*screen|layar\s*sentuh", text, re.I) else "No",
            "gpu": extract_spec(text, [
                r"VGA[:\s]+([\w\s]+?)(?:,|\n|RAM|$)",
                r"(NVIDIA\s+[\w\s]+?)(?:,|\n|RAM|$)",
                r"(Intel\s+(?:UHD|Iris\s*Xe?)\s*[\w\s]*?)(?:,|\n|RAM|$)",
            ]),
            "gpu_type": "Dedicated" if re.search(r"NVIDIA|GTX|RTX|Quadro", text, re.I) else "Integrated",
            "os": extract_spec(text, [
                r"OS[:\s]+(Windows\s*\d+[\w\s]*)",
                r"(Windows\s*\d+\s*(?:PRO|HOME|64\s*bit)?)",
            ]),
            "battery_hours": extract_spec(text, [r"(\d+)\s*[-]\s*\d+\s*[Jj]am"]),
            "condition": "Used",
            "error": None,
        }
    except Exception as e:
        return {"url": url, "error": str(e)[:80]}

# Thread-safe counter
lock = threading.Lock()
completed = [0]

def worker(worker_id, q, results):
    driver = make_driver()
    try:
        while True:
            try:
                url = q.get_nowait()
            except Exception:
                break
            data = parse_page(driver, url)
            # Retry once if empty
            if not data.get("name") and not data.get("error"):
                time.sleep(3)
                data = parse_page(driver, url)
            with lock:
                results[url] = data
                completed[0] += 1
                n = completed[0]
                total = q.maxsize + len(results) - q.qsize()
                status = data.get('name', data.get('error', 'empty'))[:40] if data else 'empty'
                print(f"  [W{worker_id}] [{n}] {status}")
            q.task_done()
            time.sleep(0.5)
    finally:
        driver.quit()

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    data_by_url = {r["url"]: r for r in all_rows}
    missing_urls = [r["url"] for r in all_rows if not r.get("name") and not r.get("price_idr")]
    total = len(missing_urls)
    print(f"Re-scraping {total} empty rows with {NUM_WORKERS} parallel workers...")

    q = Queue(maxsize=total)
    for url in missing_urls:
        q.put(url)

    results = {}
    threads = []
    for i in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(i+1, q, results), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(1)  # stagger startup

    q.join()
    for t in threads:
        t.join(timeout=5)

    # Merge results back
    data_by_url.update(results)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for r in all_rows:
            writer.writerow(data_by_url.get(r["url"], r))

    filled = sum(1 for r in data_by_url.values() if r.get("name"))
    still_empty = sum(1 for r in data_by_url.values() if not r.get("name"))
    print(f"\nDone! {filled} rows with data, {still_empty} still empty.")

if __name__ == "__main__":
    main()
