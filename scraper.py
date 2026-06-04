import re
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

OUTPUT_FILE = "laptops_raw.csv"
STORE_URL = "https://www.tokopedia.com/specialistlaptop/product/page/{}"

# ── Browser setup ────────────────────────────────────────────────────────────

def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

def scroll_full_page(driver):
    for _ in range(15):
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(0.8)
    time.sleep(2)

# ── Step 1: collect all product URLs ────────────────────────────────────────

def collect_product_links(driver):
    all_links = set()
    page = 1
    while True:
        url = STORE_URL.format(page)
        print(f"  Scanning page {page}...")
        driver.get(url)
        time.sleep(6)
        scroll_full_page(driver)

        src = driver.page_source
        raw = re.findall(
            r'href="(https://www\.tokopedia\.com/specialistlaptop/[^"]+)"', src
        )
        found = set()
        for l in raw:
            clean = l.split("?")[0].split("&")[0]
            if "/product" in clean:
                continue
            if clean.rstrip("/") in (
                "https://www.tokopedia.com/specialistlaptop",
            ):
                continue
            if re.search(r"/specialistlaptop/[a-z0-9\-]+$", clean):
                found.add(clean)

        new = found - all_links
        print(f"    {len(found)} links on page, {len(new)} new")
        if not new:
            break
        all_links.update(found)

        if not re.search(rf"/product/page/{page + 1}", src):
            break
        page += 1

    print(f"  Total product links collected: {len(all_links)}")
    return sorted(all_links)

# ── Step 2: parse individual product page ───────────────────────────────────

def parse_price(soup):
    el = soup.find(attrs={"data-testid": "lblPDPDetailProductPrice"})
    if el:
        digits = re.sub(r"[^\d]", "", el.text)
        return int(digits) if digits else None
    return None

def parse_name(soup):
    el = soup.find(attrs={"data-testid": "lblPDPDetailProductName"})
    if el:
        return el.text.strip()
    h1 = soup.find("h1")
    return h1.text.strip() if h1 else None

def parse_sold(soup):
    el = soup.find(attrs={"data-testid": "lblPDPDetailProductSoldCounter"})
    if el:
        digits = re.search(r"[\d,]+", el.text)
        return digits.group().replace(",", "") if digits else None
    return None

def parse_rating(soup):
    el = soup.find(attrs={"data-testid": "lblPDPDetailProductRatingNumber"})
    return el.text.strip() if el else None

def extract_spec(text, patterns):
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def parse_description(soup):
    desc_el = soup.find(attrs={"data-testid": "lblPDPDescriptionProduk"})
    if not desc_el:
        return {}
    text = desc_el.get_text(separator=" ", strip=True)

    specs = {}

    # Brand — from product name or description
    name_el = soup.find(attrs={"data-testid": "lblPDPDetailProductName"})
    name_text = name_el.text if name_el else ""
    brand_match = re.search(
        r"\b(Lenovo|Dell|HP|Asus|Acer|MSI|Apple|Samsung|Toshiba|Sony|Fujitsu|Huawei|LG|Razer)\b",
        name_text, re.IGNORECASE
    )
    specs["brand"] = brand_match.group(1).title() if brand_match else None

    # CPU / Processor
    specs["cpu"] = extract_spec(text, [
        r"Intel\s+Core\s+(i\d[\w\-\s]+?)(?:\s+\d+\.\d+\s*GHz|\s*,|\s*\n|RAM|Memory)",
        r"AMD\s+Ryzen\s+([\d\w\s\-]+?)(?:\s+\d+\.\d+\s*GHz|\s*,|\s*\n|RAM|Memory)",
        r"Processor[:\s]+([\w\s\-]+?)(?:,|\n|RAM|Memory)",
        r"(Intel\s+Core\s+i\d[\w\s\-]+?\d{4}[A-Z0-9]*)",
        r"(AMD\s+Ryzen\s+\d[\w\s]+?\d{4}[A-Z0-9]*)",
        r"(Intel\s+Core\s+[iUH]\d[\w\-]+)",
    ])

    # Full CPU line for reference
    cpu_line = extract_spec(text, [
        r"(Intel\s+Core\s+i\d[^\n\r,]{3,40})",
        r"(AMD\s+Ryzen[^\n\r,]{3,40})",
    ])
    specs["cpu_full"] = cpu_line

    # RAM
    specs["ram_gb"] = extract_spec(text, [
        r"RAM[:\s]+(\d+)\s*GB",
        r"Memory[:\s]+(?:DDR\d\s+)?(\d+)\s*GB",
        r"(\d+)\s*GB\s+(?:DDR\d|RAM)",
    ])

    # Storage type and size
    storage_text = extract_spec(text, [
        r"(SSD\s*(?:NVME|NVMe|M\.2)?\s*[\d,\-\/\s]+(?:GB|TB)[^\n\r,]{0,30})",
        r"(HDD\s*[\d,\-\/\s]+(?:GB|TB)[^\n\r,]{0,30})",
        r"Storage[:\s]+([\w\s\-\/]+(?:GB|TB))",
    ])
    specs["storage_raw"] = storage_text

    ssd_size = extract_spec(text, [
        r"SSD\s*(?:NVME|NVMe|M\.2)?\s*(\d+)\s*(?:GB|TB)",
        r"(\d+)\s*GB\s+SSD",
        r"(\d+)\s*TB\s+SSD",
    ])
    specs["ssd_gb"] = ssd_size

    specs["storage_type"] = "SSD" if re.search(r"\bSSD\b", text, re.I) else (
        "HDD" if re.search(r"\bHDD\b", text, re.I) else None
    )
    specs["nvme"] = "Yes" if re.search(r"\bNVME\b|\bNVMe\b|\bM\.2\b", text, re.I) else "No"

    # Screen size
    specs["screen_inch"] = extract_spec(text, [
        r"Layar\s+([\d\.]+)\s*inch",
        r"([\d\.]+)\s*[\"\"]\s*(?:inch|FHD|HD|IPS|LCD|LED)",
        r"([\d\.]+)\s*inch",
        r"(\d{2})\s*inch",
    ])

    # Resolution / display type
    specs["resolution"] = extract_spec(text, [
        r"(\d{3,4}\s*[xX]\s*\d{3,4})",
        r"(Full\s*HD|FHD|HD|QHD|4K|WUXGA|WXGA)",
    ])
    specs["display_type"] = "IPS" if re.search(r"\bIPS\b", text, re.I) else (
        "TN" if re.search(r"\bTN\b", text, re.I) else None
    )
    specs["touchscreen"] = "Yes" if re.search(
        r"touch\s*screen|layar\s*sentuh", text, re.I
    ) else "No"

    # GPU
    gpu = extract_spec(text, [
        r"VGA[:\s]+([\w\s]+?)(?:,|\n|RAM|Memory|$)",
        r"(NVIDIA\s+[\w\s]+?)(?:,|\n|RAM|$)",
        r"(AMD\s+Radeon\s+[\w\s]+?)(?:,|\n|RAM|$)",
        r"(Intel\s+(?:UHD|Iris\s*Xe?)\s*[\w\s]*?)(?:,|\n|RAM|$)",
    ])
    specs["gpu"] = gpu.strip() if gpu else None
    specs["gpu_type"] = "Dedicated" if re.search(
        r"NVIDIA|GTX|RTX|Quadro|AMD\s+Radeon\s+R[X\d]", text, re.I
    ) else "Integrated"

    # OS
    specs["os"] = extract_spec(text, [
        r"OS[:\s]+(Windows\s*\d+[\w\s]*)",
        r"(Windows\s*\d+\s*(?:PRO|HOME|64\s*bit)?)",
    ])

    # Battery (hours)
    specs["battery_hours"] = extract_spec(text, [
        r"(\d+)\s*[-–]\s*\d+\s*[Jj]am",
        r"[Bb]aterai\s*[:\s]+(?:[Ee]stimasi\s+)?(\d+)",
    ])

    # Condition
    specs["condition"] = "Used"

    return specs

def scrape_product(driver, url):
    try:
        driver.get(url)
        time.sleep(6)
        for _ in range(8):
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(0.4)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        data = {
            "url": url,
            "name": parse_name(soup),
            "price_idr": parse_price(soup),
            "sold_count": parse_sold(soup),
            "rating": parse_rating(soup),
        }
        data.update(parse_description(soup))
        return data
    except Exception as e:
        print(f"    ERROR on {url}: {e}")
        return {"url": url, "error": str(e)}

# ── Main ─────────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "url", "name", "price_idr", "sold_count", "rating",
    "brand", "cpu", "cpu_full", "ram_gb", "storage_raw",
    "ssd_gb", "storage_type", "nvme", "screen_inch",
    "resolution", "display_type", "touchscreen",
    "gpu", "gpu_type", "os", "battery_hours", "condition",
    "error",
]

def main():
    driver = make_driver()
    try:
        print("=== Step 1: Collecting product links ===")
        links = collect_product_links(driver)

        print(f"\n=== Step 2: Scraping {len(links)} product pages ===")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()

            for i, url in enumerate(links, 1):
                print(f"  [{i}/{len(links)}] {url.split('/')[-1][:60]}")
                data = scrape_product(driver, url)
                writer.writerow(data)
                f.flush()
                time.sleep(1)  # polite delay

        print(f"\nDone! Data saved to {OUTPUT_FILE}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
