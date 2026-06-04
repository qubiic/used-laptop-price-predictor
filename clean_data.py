import csv
import re

INPUT_FILE = "laptops_raw.csv"
OUTPUT_FILE = "laptops_clean.csv"

FIELDNAMES = [
    "name", "brand", "price_idr",
    "cpu_brand", "cpu_gen", "cpu_tier", "cpu_model",
    "ram_gb", "ssd_gb", "storage_type", "nvme",
    "screen_inch", "resolution", "display_type", "touchscreen",
    "gpu_type", "os", "sold_count", "rating",
]

KNOWN_LAPTOP_BRANDS = (
    "Lenovo", "Dell", "HP", "Asus", "Acer", "MSI", "Apple",
    "Samsung", "Toshiba", "Sony", "Fujitsu", "Huawei", "LG", "Razer",
)

NON_LAPTOP_PATTERN = re.compile(
    r"\b(charger|adaptor|adapter|ram\s*tambahan|obral\s*ram|"
    r"dekstop|desktop|pc\s*dekstop|pc\s*desktop|mini\s*pc|"
    r"pokemon|tas\s*laptop|paket\s*komputer|"
    r"komputer\s*bekas\s*branded|thinkcentre|optiplex|"
    r"sff\b|small\s*form\s*factor|cpu\s*only|hdd\s*external|"
    r"keyboard|mouse|charger|baterai\s*saja|battery\s*only)\b",
    re.IGNORECASE,
)


def is_laptop(row):
    name = (row.get("name") or "").strip()
    if not name:
        return False
    if NON_LAPTOP_PATTERN.search(name):
        return False
    price = row.get("price_idr")
    if price:
        try:
            if int(price) < 500_000:
                return False
        except (TypeError, ValueError):
            pass
    return True


def infer_cpu_gen_from_model(model_str):
    if not model_str:
        return None
    model_str = model_str.strip().upper()
    m = re.match(r"^(\d{4,5})", model_str)
    if not m:
        return None
    num = m.group(1)
    if len(num) == 4:
        first = int(num[0])
        return first if 2 <= first <= 9 else None
    if len(num) == 5:
        first_two = int(num[:2])
        return first_two if 10 <= first_two <= 14 else None
    return None


def extract_brand(name):
    m = re.search(
        r"\b(" + "|".join(KNOWN_LAPTOP_BRANDS) + r")\b",
        name, re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1).title()


def extract_cpu(name, cpu_raw="", cpu_full=""):
    out = {"cpu_brand": None, "cpu_tier": None, "cpu_gen": None, "cpu_model": None}
    combined = " ".join(filter(None, [name, str(cpu_raw or ""), str(cpu_full or "")]))

    # Pentium / Celeron — explicit model like N5000, 3865u
    m = re.search(r"\b(Pentium|Celeron)\b[\s\w]*?(\b[A-Z]?\d{4}[A-Z]?\b)?", combined, re.I)
    if m:
        out["cpu_brand"] = "Intel"
        out["cpu_tier"] = m.group(1).lower()
        out["cpu_model"] = m.group(2)
        return out

    # Core 2 Duo
    if re.search(r"Core\s*2\s*Duo|Core2Duo", combined, re.I):
        out["cpu_brand"] = "Intel"
        out["cpu_tier"] = "core2duo"
        return out

    # AMD Ryzen
    m = re.search(r"Ryzen\s*(\d)\s*(?:Pro\s*)?(\d{4}[A-Z0-9]*)?", combined, re.I)
    if m:
        out["cpu_brand"] = "AMD"
        out["cpu_tier"] = f"ryzen{m.group(1)}"
        out["cpu_model"] = m.group(2)
        if m.group(2):
            out["cpu_gen"] = infer_cpu_gen_from_model(m.group(2))
        return out

    # Intel Core iX — supports "Core i5", "Corei5", "Core i5 4300u", "Core i5 Gen 8", "i5 8th Gen"
    tier_match = re.search(r"\b(?:Core\s*)?(i[3579])\b", combined, re.I)
    if tier_match:
        out["cpu_brand"] = "Intel"
        out["cpu_tier"] = tier_match.group(1).lower()

        # Explicit "Gen N" / "Gen-N" / "8th Gen" / "Generasi N"
        gen_m = re.search(
            r"(?:Gen\s*[-]?\s*|Generasi\s*)(\d{1,2})|\b(\d{1,2})(?:st|nd|rd|th)\s*Gen\b",
            combined, re.I,
        )
        if gen_m:
            gen_val = int(gen_m.group(1) or gen_m.group(2))
            if 2 <= gen_val <= 14:
                out["cpu_gen"] = gen_val

        # Explicit CPU model number: i5-4300U, i7 8650u, i5 1145G7, i7-1185G7
        model_m = re.search(
            r"i[3579][\s\-]+(\d{4,5}[A-Z]?\d?[A-Z]?)\b",
            combined, re.I,
        )
        if model_m:
            out["cpu_model"] = model_m.group(1).upper()
            if not out["cpu_gen"]:
                out["cpu_gen"] = infer_cpu_gen_from_model(model_m.group(1))

    return out


def extract_ram(name, ram_raw=""):
    # Look for RAM N GB / NGB RAM / NGB DDR — prefer name first to catch e.g. "RAM 16GB"
    for source in (name, str(ram_raw or "")):
        if not source:
            continue
        m = re.search(
            r"(?:RAM\s*)?(\d{1,2})\s*GB(?:\s*(?:RAM|DDR\d?))?",
            source, re.I,
        )
        if m:
            v = int(m.group(1))
            if v in (2, 4, 6, 8, 12, 16, 32, 64):
                return v
        # Just a number in ram_raw (e.g. "8")
        if source.strip().isdigit():
            v = int(source.strip())
            if v in (2, 4, 6, 8, 12, 16, 32, 64):
                return v
    return None


def extract_storage(name, ssd_raw="", storage_raw=""):
    """Returns (ssd_gb, storage_type, nvme_flag).

    The Tokopedia listing format puts the actual final spec after a dash:
    'Laptop ... SSD 240 ... - SSD 128GB, 8 gb' — the part after ' - ' wins.
    """
    nvme = 0
    storage_type = None

    combined = " ".join(filter(None, [name, str(ssd_raw or ""), str(storage_raw or "")]))
    if re.search(r"\bNVME\b|\bNVMe\b|\bM\.?2\b", combined, re.I):
        nvme = 1

    # Prefer post-dash spec from name (seller's authoritative variant)
    post_dash = None
    if " - " in name:
        post_dash = name.rsplit(" - ", 1)[1]

    candidates = []
    if post_dash:
        candidates.append(post_dash)
    candidates.append(name)
    if ssd_raw and str(ssd_raw).strip().isdigit():
        candidates.append(f"SSD {int(ssd_raw)}GB")
    if storage_raw:
        candidates.append(str(storage_raw))

    for source in candidates:
        # SSD / NVMe TB
        m = re.search(r"(?:SSD|NVME|NVMe|M\.?2)\s*(\d+(?:\.\d+)?)\s*TB", source, re.I)
        if m:
            return int(float(m.group(1)) * 1024), "SSD", nvme or (1 if "NVME" in source.upper() else 0)
        # SSD GB
        m = re.search(r"(?:SSD|NVME|NVMe|M\.?2)\s*(\d{2,4})\s*(?:GB)?", source, re.I)
        if m:
            v = int(m.group(1))
            if 32 <= v <= 4096:
                return v, "SSD", nvme or (1 if re.search(r"NVME|NVMe|M\.?2", source, re.I) else 0)
        # "N GB SSD"
        m = re.search(r"(\d{2,4})\s*GB\s*SSD", source, re.I)
        if m:
            v = int(m.group(1))
            if 32 <= v <= 4096:
                return v, "SSD", nvme
        # HDD GB
        m = re.search(r"(?:HDD)\s*(\d{2,4})\s*(?:GB)?", source, re.I)
        if m:
            v = int(m.group(1))
            if 80 <= v <= 4096:
                return v, "HDD", 0
        m = re.search(r"(\d{2,4})\s*GB\s*HDD", source, re.I)
        if m:
            v = int(m.group(1))
            if 80 <= v <= 4096:
                return v, "HDD", 0

    # Naked storage like "Latitude E5450 ... 256" — try if SSD/HDD keyword exists in name
    if re.search(r"\bSSD\b", name, re.I):
        storage_type = "SSD"
    elif re.search(r"\bHDD\b", name, re.I):
        storage_type = "HDD"

    return None, storage_type, nvme


def extract_screen(name, screen_raw=""):
    # screen_raw may be a clean number
    if screen_raw:
        try:
            v = float(str(screen_raw).strip())
            if 10 <= v <= 20:
                return v
        except (TypeError, ValueError):
            pass

    # Try name patterns: 14", 14 inch, 14"FHD, 13.3 inch, 15.6"
    patterns = [
        r"(\d{2}(?:\.\d)?)\s*(?:inch|in\b|\")",
        r"(\d{2}(?:\.\d)?)[\"”]\s*(?:FHD|HD|IPS|LCD|LED)",
    ]
    for pat in patterns:
        m = re.search(pat, name, re.I)
        if m:
            v = float(m.group(1))
            if 10 <= v <= 20:
                return v
    return None


def extract_resolution(name, res_raw=""):
    combined = " ".join(filter(None, [name, str(res_raw or "")]))
    if re.search(r"1920\s*[xX]\s*1080|\bFHD\b|Full\s*HD", combined, re.I):
        return "FHD"
    if re.search(r"2560\s*[xX]\s*1440|\bQHD\b|\bWQHD\b", combined, re.I):
        return "QHD"
    if re.search(r"3840\s*[xX]\s*2160|\b4K\b|\bUHD\b", combined, re.I):
        return "4K"
    if re.search(r"1366\s*[xX]\s*768|\bHD\b", combined, re.I):
        return "HD"
    return None


def extract_display_type(name, display_raw=""):
    combined = " ".join(filter(None, [name, str(display_raw or "")]))
    if re.search(r"\bIPS\b", combined, re.I):
        return "IPS"
    if re.search(r"\bTN\b", combined, re.I):
        return "TN"
    return None


def extract_touchscreen(name, touch_raw=""):
    if touch_raw == "Yes":
        return 1
    if re.search(r"touch\s*screen|touchscreen|layar\s*sentuh|2\s*in\s*1|yoga", name, re.I):
        return 1
    return 0


def extract_gpu_type(name, gpu_raw="", gpu_type_raw=""):
    combined = " ".join(filter(None, [name, str(gpu_raw or ""), str(gpu_type_raw or "")]))
    if re.search(
        r"NVIDIA|GeForce|GTX|RTX|Quadro|MX\d{3}|AMD\s*Radeon\s*R[X\d]|Radeon\s*\d{3}|VGA\s*Nvidia|VGA\s*AMD",
        combined, re.I,
    ):
        return "Dedicated"
    return "Integrated"


def extract_os(name, os_raw=""):
    combined = " ".join(filter(None, [name, str(os_raw or "")]))
    if re.search(r"Win(?:dows)?\s*11", combined, re.I):
        return "Windows 11"
    if re.search(r"Win(?:dows)?\s*10", combined, re.I):
        return "Windows 10"
    if re.search(r"Win(?:dows)?\s*8", combined, re.I):
        return "Windows 8"
    if re.search(r"Win(?:dows)?\s*7", combined, re.I):
        return "Windows 7"
    return None


def clean_row(row):
    name = (row.get("name") or "").strip()

    cpu = extract_cpu(name, row.get("cpu"), row.get("cpu_full"))
    ram_gb = extract_ram(name, row.get("ram_gb"))
    ssd_gb, storage_type, nvme = extract_storage(
        name, row.get("ssd_gb"), row.get("storage_raw"),
    )
    if not storage_type:
        storage_type = row.get("storage_type") if row.get("storage_type") in ("SSD", "HDD") else "SSD"

    screen_inch = extract_screen(name, row.get("screen_inch"))
    resolution = extract_resolution(name, row.get("resolution"))
    display_type = extract_display_type(name, row.get("display_type"))
    touchscreen = extract_touchscreen(name, row.get("touchscreen"))
    gpu_type = extract_gpu_type(name, row.get("gpu"), row.get("gpu_type"))
    os_val = extract_os(name, row.get("os"))
    brand = extract_brand(name) or (row.get("brand") if row.get("brand") else None)

    price = None
    if row.get("price_idr"):
        try:
            price = int(row["price_idr"])
        except (TypeError, ValueError):
            pass

    sold = None
    if row.get("sold_count"):
        try:
            sold = int(re.sub(r"[^\d]", "", str(row["sold_count"])))
        except ValueError:
            pass

    rating = None
    if row.get("rating"):
        try:
            rating = float(row["rating"])
        except (TypeError, ValueError):
            pass

    return {
        "name": name,
        "brand": brand,
        "price_idr": price,
        "cpu_brand": cpu["cpu_brand"],
        "cpu_gen": cpu["cpu_gen"],
        "cpu_tier": cpu["cpu_tier"],
        "cpu_model": cpu["cpu_model"],
        "ram_gb": ram_gb,
        "ssd_gb": ssd_gb,
        "storage_type": storage_type,
        "nvme": nvme,
        "screen_inch": screen_inch,
        "resolution": resolution,
        "display_type": display_type,
        "touchscreen": touchscreen,
        "gpu_type": gpu_type,
        "os": os_val,
        "sold_count": sold,
        "rating": rating,
    }


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Raw rows: {len(rows)}")

    laptops = [r for r in rows if is_laptop(r)]
    print(f"After filtering non-laptops/desktops/accessories: {len(laptops)}")

    cleaned = [clean_row(r) for r in laptops]

    # Drop rows missing critical fields. RAM, brand, price are non-negotiable.
    critical = ["price_idr", "ram_gb", "brand"]
    valid = [r for r in cleaned if all(r.get(f) for f in critical)]
    print(f"After dropping rows missing critical fields (price/ram/brand): {len(valid)}")

    print("\nField coverage:")
    for field in FIELDNAMES:
        count = sum(1 for r in valid if r.get(field) not in (None, ""))
        pct = count / len(valid) * 100 if valid else 0
        print(f"  {field:15s}: {count:3d}/{len(valid)} ({pct:5.1f}%)")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(valid)

    print(f"\nClean dataset saved to {OUTPUT_FILE} ({len(valid)} rows)")

    prices = [r["price_idr"] for r in valid]
    print(f"Price range: Rp{min(prices):,} - Rp{max(prices):,}")
    print(f"Median price: Rp{sorted(prices)[len(prices)//2]:,}")


if __name__ == "__main__":
    main()
