import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

MODEL_PATH = Path("best_model.pkl")
DATA_PATH = Path("laptops_clean.csv")

BRANDS = ["Lenovo", "Dell", "Hp", "Asus", "Toshiba", "Fujitsu"]
CPU_TIERS = ["i3", "i5", "i7", "i9", "ryzen5", "ryzen7", "celeron", "pentium", "core2duo"]
RAM_OPTIONS = [2, 4, 8, 16, 32]
SSD_OPTIONS = [128, 240, 256, 500, 512, 1024]
SCREEN_OPTIONS = [11.6, 12.5, 13.3, 14.0, 15.6, 17.0]

SOLD_COUNT_DEFAULT = float(np.log1p(10))
STORAGE_SSD = 1
RATING_DEFAULT = 5.0


@st.cache_resource
def load_model():
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


@st.cache_data
def load_quick_picks():
    if not DATA_PATH.exists():
        return []
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["brand", "cpu_tier", "ram_gb"]).copy()
    df["cpu_gen_key"] = df["cpu_gen"].fillna(-1).astype(int)

    groups = df.groupby(["brand", "cpu_tier", "cpu_gen_key", "ram_gb"])
    picks = []
    for (brand, tier, gen, ram), g in groups:
        if len(g) < 2:
            continue
        gen_label = f"Gen {gen}" if gen > 0 else "Gen ?"
        label = f"{brand} {tier} {gen_label}, {int(ram)}GB RAM ({len(g)} listings)"
        picks.append({
            "label": label,
            "brand": brand,
            "cpu_tier": tier,
            "cpu_gen": int(gen) if gen > 0 else 8,
            "ram_gb": int(ram),
            "ssd_gb": int(g["ssd_gb"].median()) if g["ssd_gb"].notna().any() else 256,
            "nvme": int(round(g["nvme"].mean())),
            "screen_inch": float(g["screen_inch"].median()) if g["screen_inch"].notna().any() else 14.0,
            "touchscreen": int(round(g["touchscreen"].mean())),
            "is_fhd": int((g["resolution"] == "FHD").mean() >= 0.5),
            "is_ips": int((g["display_type"] == "IPS").mean() >= 0.5),
            "gpu_type_bin": int((g["gpu_type"] != "Integrated").mean() >= 0.5),
            "has_os_label": int(g["os"].notna().mean() >= 0.5),
            "rating": float(g["rating"].median()) if g["rating"].notna().any() else 4.8,
        })
    picks.sort(key=lambda p: p["label"])
    return picks


def closest(value, options):
    return min(options, key=lambda x: abs(x - value))


def apply_pick(pick):
    st.session_state["brand"] = pick["brand"] if pick["brand"] in BRANDS else BRANDS[0]
    st.session_state["cpu_tier"] = pick["cpu_tier"] if pick["cpu_tier"] in CPU_TIERS else "i5"
    st.session_state["cpu_gen"] = int(np.clip(pick["cpu_gen"], 1, 12))
    st.session_state["ram_gb"] = closest(pick["ram_gb"], RAM_OPTIONS)
    st.session_state["ssd_gb"] = closest(pick["ssd_gb"], SSD_OPTIONS)
    st.session_state["screen_inch"] = closest(pick["screen_inch"], SCREEN_OPTIONS)
    st.session_state["nvme"] = bool(pick["nvme"])
    st.session_state["touchscreen"] = bool(pick["touchscreen"])
    st.session_state["is_fhd"] = bool(pick["is_fhd"])
    st.session_state["is_ips"] = bool(pick["is_ips"])
    st.session_state["gpu_type_bin"] = bool(pick["gpu_type_bin"])
    st.session_state["has_os_label"] = bool(pick["has_os_label"])


st.set_page_config(page_title="Used Laptop Price Predictor", page_icon="💻")
st.title("Used Laptop Price Predictor")
st.caption(
    "Predicts the fair market price in Rupiah (IDR) of a used laptop from its specs. "
    "Trained on 156 real Tokopedia listings. Random Forest, R² = 0.645, MAE ≈ Rp 687k."
)

model = load_model()
if model is None:
    st.error(f"Model file `{MODEL_PATH}` not found. Train the model first.")
    st.stop()

picks = load_quick_picks()

st.subheader("Quick pick (optional)")
st.write(
    "Pick a known configuration from the training data to auto-fill the spec form below, "
    "then tweak as needed. Or skip and enter specs manually."
)

pick_labels = ["-- Manual entry --"] + [p["label"] for p in picks]
chosen = st.selectbox("Known configuration", pick_labels, key="quick_pick")
if chosen != "-- Manual entry --":
    pick = next(p for p in picks if p["label"] == chosen)
    if st.button("Apply this configuration to the form"):
        apply_pick(pick)
        st.success(f"Applied: {chosen}. Adjust below if needed.")

st.divider()
st.subheader("Specs")

col1, col2 = st.columns(2)

with col1:
    brand = st.selectbox("Brand", BRANDS, key="brand")
    cpu_tier = st.selectbox("CPU tier", CPU_TIERS, key="cpu_tier")
    is_ryzen = cpu_tier in ("ryzen5", "ryzen7")
    if is_ryzen:
        cpu_gen_max = 6
        if st.session_state.get("cpu_gen", 8) > cpu_gen_max:
            st.session_state["cpu_gen"] = 4
        cpu_gen = st.slider("Ryzen generation (Zen 1–Zen 4)", 1, cpu_gen_max, key="cpu_gen",
            help="AMD Ryzen mobile chips in the dataset are Zen 2/3 era (gens 3–5). The model has not seen Ryzen 6000+ series.")
    else:
        cpu_gen = st.slider("Intel CPU generation", 1, 12, key="cpu_gen")
    ram_gb = st.selectbox("RAM (GB)", RAM_OPTIONS, key="ram_gb")
    ssd_gb = st.selectbox("SSD (GB)", SSD_OPTIONS, key="ssd_gb")
    nvme = st.checkbox("NVMe SSD", key="nvme")

with col2:
    screen_inch = st.selectbox("Screen size (inch)", SCREEN_OPTIONS, key="screen_inch")
    is_fhd = st.checkbox("Full HD display", key="is_fhd")
    is_ips = st.checkbox("IPS panel", key="is_ips")
    touchscreen = st.checkbox("Touchscreen", key="touchscreen")
    gpu_type_bin = st.checkbox("Has dedicated GPU (any model)", key="gpu_type_bin",
        help="The model only knows integrated vs dedicated. Specific GPU chips and VRAM are not captured in the training data, so a Nvidia T2000 4GB and an AMD 1GB are treated the same.")
    has_os_label = st.checkbox("Seller listed an OS", key="has_os_label")

st.divider()

if st.button("Predict Price", type="primary"):
    row = pd.DataFrame([{
        "brand": brand,
        "cpu_gen": cpu_gen,
        "cpu_tier": cpu_tier,
        "ram_gb": ram_gb,
        "ssd_gb": ssd_gb,
        "nvme": int(nvme),
        "screen_inch": screen_inch,
        "touchscreen": int(touchscreen),
        "rating": RATING_DEFAULT,
        "is_ips": int(is_ips),
        "has_os_label": int(has_os_label),
        "is_fhd": int(is_fhd),
        "storage_type_bin": STORAGE_SSD,
        "gpu_type_bin": int(gpu_type_bin),
        "sold_count_log": SOLD_COUNT_DEFAULT,
    }])

    t0 = time.perf_counter()
    price = float(model.predict(row)[0])
    latency_ms = (time.perf_counter() - t0) * 1000

    st.success(f"### Estimated Price: Rp {price:,.0f}")
    st.caption(
        f"Prediction took {latency_ms:.1f} ms. "
        f"Typical accuracy on test data: ±Rp 687,000 (MAE)."
    )
