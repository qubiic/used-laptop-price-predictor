# Used Laptop Price Predictor — Complete Project Guide

A full walkthrough of the project from raw data collection to a deployable Streamlit web app.

**Group Members:**
- 2802392816 — Billie Godwin
- 2802393030 — Demetrius Denzell Tan
- 2802394456 — Ariya Saddhana Lius

---

## Table of Contents

1. [What the project does](#1-what-the-project-does)
2. [The complete pipeline](#2-the-complete-pipeline)
3. [Step 1 — Data collection (web scraping)](#step-1--data-collection-web-scraping)
4. [Step 2 — Data cleaning](#step-2--data-cleaning)
5. [Step 3 — Machine learning (notebook)](#step-3--machine-learning-notebook)
6. [Step 4 — Model results & backtesting](#step-4--model-results--backtesting)
7. [Step 5 — Streamlit web app (next task)](#step-5--streamlit-web-app-next-task)
8. [Step 6 — Deployment](#step-6--deployment)
9. [Step 7 — User testing](#step-7--user-testing)
10. [Project checklist](#project-checklist)
11. [File reference](#file-reference)

---

## 1. What the project does

The project predicts the **fair market price (in IDR)** of a used laptop based on its hardware specs (brand, CPU, RAM, SSD, screen, GPU, etc.).

It's trained on **156 real used-laptop listings scraped from a Tokopedia store** ([Specialist Laptop Second](https://www.tokopedia.com/specialistlaptop/product/)), so it reflects actual second-hand market pricing in Indonesia — not new retail prices.

**Use case:** A buyer enters the specs of a laptop they're considering, and the app returns an estimated fair price. If the seller's asking price is much higher than the model's estimate, the buyer knows they may be overpaying.

---

## 2. The complete pipeline

```
Tokopedia store
      ↓
[scraper.py]              → laptops_raw.csv  (301 raw scraped rows)
      ↓
[clean_data.py]           → laptops_clean.csv (156 cleaned laptop rows)
      ↓
[used_laptop_price_prediction.ipynb]
   ├── EDA
   ├── Train Linear / Random Forest / SVR
   ├── Evaluate + backtest
   └── Save best model
      ↓
   best_model.pkl + model_metadata.json
      ↓
[app.py — Streamlit]      ← TO BE BUILT
      ↓
Live web app for users
```

---

## Step 1 — Data collection (web scraping)

**File:** [scraper.py](scraper.py)

**What it does:** Uses Selenium (headless Chrome) and BeautifulSoup to:
1. Visit every product page in the Tokopedia store
2. Extract product name, price, sold count, rating, and the full product description
3. Parse hardware specs (CPU, RAM, SSD, screen, GPU, OS, etc.) from the description text using regex
4. Save everything to `laptops_raw.csv`

**Output:** 301 raw rows in `laptops_raw.csv`. Many rows had parsing failures because some pages failed to load and some descriptions used inconsistent formatting.

**To re-run (if you want fresh data):**
```bash
python scraper.py
python rescrape_parallel.py   # retries pages that failed the first time
```

> Note: Tokopedia rate-limits aggressive scraping. The scraper uses polite delays. Running it takes ~30 minutes.

---

## Step 2 — Data cleaning

**File:** [clean_data.py](clean_data.py)

**What it does:**
1. **Filters out non-laptops** — removes chargers, RAM modules, desktops (Optiplex, ThinkCentre), accessories
2. **Extracts specs from product titles** — sellers consistently encode specs like `"Core i5 Gen 8 RAM 16GB SSD 512 IPS"` in the title, so the cleaner mines the title aggressively
3. **Normalizes CPU info** — recognizes `Core i5`, `Corei5`, `i5`, plus generation patterns like `Gen 8`, `8th Gen`, `Generasi 11`, and infers generation from model number (e.g. `8265U` → gen 8)
4. **Handles Tokopedia's "post-dash" pattern** — listings often end with `... - SSD 128GB, 4 gb` where the seller specifies the actual variant after the dash; the cleaner prefers post-dash values
5. **Drops rows missing critical fields** (price, RAM, brand)

**Output:** 156 clean rows in `laptops_clean.csv` with the following coverage:

| Field | Coverage |
|---|---|
| brand, price_idr, ram_gb, storage_type, nvme, touchscreen, gpu_type | 100% |
| sold_count | 96% |
| cpu_tier, cpu_brand | 97% |
| ssd_gb | 95% |
| rating | 94% |
| resolution | 86% |
| cpu_gen | 84% |
| cpu_model | 74% |
| screen_inch | 73% |
| display_type | 51% |
| os | 39% |

Remaining missing values are handled later via **median imputation** for numeric features and **binary flags** for categorical ones (e.g., `has_os_label = 0` if OS missing).

**To re-run cleaning:**
```bash
python clean_data.py
```

---

## Step 3 — Machine learning (notebook)

**File:** [used_laptop_price_prediction.ipynb](used_laptop_price_prediction.ipynb)

The notebook is organized into 10 sections:

| Section | Purpose |
|---|---|
| 1. Setup | Imports and config |
| 2. Data Loading | Loads `laptops_clean.csv`, checks shape and dtypes |
| 3. Exploratory Data Analysis | Price distribution, price-vs-spec boxplots, correlation heatmap |
| 4. Preprocessing & Feature Engineering | Creates binary flags (`is_ips`, `is_fhd`, `has_os_label`, etc.), log-transforms `sold_count`, groups rare CPU tiers |
| 5. Train/Test Split | 80/20 split (124 train / 32 test) |
| 6. Preprocessing Pipeline | Median imputation + standard scaling for numerics; mode imputation + one-hot encoding for categoricals (wrapped in a sklearn `ColumnTransformer`) |
| 7. Model Training | Trains 3 models: Linear Regression (baseline), Random Forest (GridSearchCV), SVR (GridSearchCV) |
| 8. Evaluation | MAE, RMSE, R²; actual-vs-predicted plots; residual analysis; feature importances; cross-validation |
| 9. Save Best Model | Saves `best_model.pkl` and `model_metadata.json` |
| 10. Backtesting | Per-laptop predicted-vs-actual table for all 32 test laptops, accuracy buckets, error distribution charts |

**To re-run training:**
Open the notebook in Jupyter/VS Code and run all cells, or:
```bash
python -m jupyter nbconvert --to notebook --execute --inplace used_laptop_price_prediction.ipynb
```

---

## Step 4 — Model results & backtesting

The Random Forest (tuned) was the best performer:

| Model | MAE | RMSE | R² |
|---|---|---|---|
| Linear Regression (Baseline) | see notebook | see notebook | see notebook |
| **Random Forest (Tuned)** | **Rp 686,669** | **Rp 1,091,164** | **0.645** |
| SVR (Tuned) | see notebook | see notebook | see notebook |

**Hyperparameters (best):** `n_estimators=200, max_depth=10, min_samples_leaf=2`

**Practical meaning:**
- The model explains ~65% of the variance in used laptop prices
- On average, predictions are within **Rp 687,000** of the actual listing price (about 17% of the median price of Rp 4M)
- For a Rp 5M laptop, expect predictions roughly between Rp 4.3M and Rp 5.7M

**Backtesting (Section 10 of the notebook):** Each of the 32 test laptops gets a per-row predicted-vs-actual comparison. ~40% land within 10% of the actual price ("Great"), ~35% within 10–25% ("OK"), the rest are wider misses on unusual configurations.

---

## Step 5 — Streamlit web app (next task)

**Goal:** A simple one-page web app where a user picks laptop specs from dropdowns/sliders and gets an instant price estimate.

### Files needed for the app

Your friend needs these files to build the app:

- `best_model.pkl` — the trained model
- `model_metadata.json` — feature names (helpful for sanity-checking UI fields)
- `laptops_clean.csv` (optional) — useful for getting realistic example values and for testing

### Required UI fields

These must match the model's feature names exactly:

| Field | UI Control | Allowed Values |
|---|---|---|
| `brand` | Selectbox | Lenovo, Dell, Hp, Toshiba, Asus, Acer, Fujitsu |
| `cpu_tier` | Selectbox | i5, i7, ryzen, other |
| `cpu_gen` | Slider (1–12) or Selectbox | Optional — defaults to median if blank |
| `ram_gb` | Selectbox | 2, 4, 8, 16, 32 |
| `ssd_gb` | Selectbox | 128, 240, 256, 512, 1024 |
| `nvme` | Checkbox | NVMe SSD? |
| `screen_inch` | Selectbox | 12.5, 13.3, 14, 15.6 |
| `is_fhd` | Checkbox | Full HD display? |
| `is_ips` | Checkbox | IPS panel? |
| `touchscreen` | Checkbox | Touchscreen? |
| `gpu_type_bin` | Checkbox | Dedicated GPU? |
| `storage_type_bin` | Checkbox (default on) | SSD (1) vs HDD (0) |
| `rating` | Slider 4.0–5.0 | Seller rating (default 4.8) |
| `has_os_label` | Checkbox | Did the seller list an OS? |
| `sold_count_log` | Hidden | Default to `log1p(10) ≈ 2.4` |

### Prediction code

```python
import streamlit as st
import joblib
import pandas as pd
import numpy as np

# Load the trained model once
model = joblib.load('best_model.pkl')

st.title('Used Laptop Price Predictor')

# Build UI...
brand        = st.selectbox('Brand', ['Lenovo', 'Dell', 'Hp', 'Toshiba', 'Asus', 'Acer', 'Fujitsu'])
cpu_tier     = st.selectbox('CPU Tier', ['i5', 'i7', 'ryzen', 'other'])
cpu_gen      = st.slider('CPU Generation', 1, 12, 8)
ram_gb       = st.selectbox('RAM (GB)', [2, 4, 8, 16, 32], index=2)
ssd_gb       = st.selectbox('SSD (GB)', [128, 240, 256, 512, 1024], index=2)
nvme         = st.checkbox('NVMe SSD?')
screen_inch  = st.selectbox('Screen Size (inch)', [12.5, 13.3, 14, 15.6], index=2)
is_fhd       = st.checkbox('Full HD?')
is_ips       = st.checkbox('IPS Panel?')
touchscreen  = st.checkbox('Touchscreen?')
dedicated_gpu = st.checkbox('Dedicated GPU?')
has_os_label = st.checkbox('Seller listed OS?', value=True)
rating       = st.slider('Seller Rating', 4.0, 5.0, 4.8, step=0.1)

if st.button('Predict Price'):
    input_data = pd.DataFrame([{
        'brand': brand,
        'cpu_tier': cpu_tier,
        'cpu_gen': cpu_gen,
        'ram_gb': ram_gb,
        'ssd_gb': ssd_gb,
        'nvme': int(nvme),
        'screen_inch': screen_inch,
        'touchscreen': int(touchscreen),
        'rating': rating,
        'is_ips': int(is_ips),
        'has_os_label': int(has_os_label),
        'is_fhd': int(is_fhd),
        'storage_type_bin': 1,
        'gpu_type_bin': int(dedicated_gpu),
        'sold_count_log': np.log1p(10),
    }])
    prediction = model.predict(input_data)[0]
    st.success(f"Estimated Price: **Rp {prediction:,.0f}**")
```

### Local setup

```bash
pip install streamlit pandas scikit-learn joblib numpy
streamlit run app.py
```

> **Important:** The model was trained on **scikit-learn 1.8.0**. Use the same version (or very close) when loading the `.pkl`, otherwise joblib may throw version-mismatch warnings.

---

## Step 6 — Deployment

Two free options:

**Option A: Streamlit Community Cloud (recommended)**
1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account and pick this repo
4. Set entry point to `app.py`
5. Add a `requirements.txt` with: `streamlit`, `pandas`, `scikit-learn==1.8.0`, `joblib`, `numpy`
6. Click Deploy

**Option B: Run locally and share via ngrok**
```bash
streamlit run app.py
ngrok http 8501
```

---

## Step 7 — User testing

Per the proposal, conduct usability testing with **minimum 5 users**:

1. Give each user a real laptop (or spec sheet)
2. Ask them to use the app to get a price estimate
3. Collect feedback on:
   - Ease of use
   - Whether the predicted price felt reasonable
   - UI clarity (any fields confusing?)
4. Compare the model's prediction against the actual Tokopedia listing price for that laptop
5. Document findings for the final report

---

## Project Checklist

### Completed
- [x] Project proposal approved
- [x] Scraper built ([scraper.py](scraper.py))
- [x] Data collected (301 raw rows from Tokopedia)
- [x] Data cleaner built ([clean_data.py](clean_data.py))
- [x] Clean dataset produced (156 rows, [laptops_clean.csv](laptops_clean.csv))
- [x] EDA completed (Section 3 of notebook)
- [x] Preprocessing pipeline built (Section 6)
- [x] 3 models trained and tuned (Linear, Random Forest, SVR)
- [x] Model evaluation completed (MAE, RMSE, R², residuals, feature importance)
- [x] Best model saved ([best_model.pkl](best_model.pkl))
- [x] Backtesting on test set (Section 10)
- [x] Project documentation ([README.md](README.md), this guide)

### To Do (Streamlit & beyond)
- [ ] Create `app.py` with Streamlit UI (assigned to teammate)
- [ ] Test app locally with `streamlit run app.py`
- [ ] Verify predictions are reasonable using known laptops from `laptops_clean.csv`
- [ ] Create `requirements.txt` for deployment
- [ ] Deploy to Streamlit Community Cloud
- [ ] Conduct user testing with 5+ users
- [ ] Document user testing results
- [ ] Write final report
- [ ] Prepare presentation slides

---

## File Reference

| File | Purpose | Needed for Streamlit? |
|---|---|---|
| [README.md](README.md) | Project overview | No |
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | This file — full project walkthrough | No |
| [Proposal ML.pdf](Proposal%20ML.pdf) | Original course proposal | No |
| [scraper.py](scraper.py) | Tokopedia scraper | No (only if re-scraping) |
| [rescrape_parallel.py](rescrape_parallel.py) | Retry failed scrapes | No (only if re-scraping) |
| [clean_data.py](clean_data.py) | Cleans raw data into ML-ready CSV | No (only if re-cleaning) |
| [laptops_raw.csv](laptops_raw.csv) | Raw scraped data (301 rows) | No |
| [laptops_clean.csv](laptops_clean.csv) | Clean dataset (156 rows, 19 cols) | Optional (for testing) |
| [used_laptop_price_prediction.ipynb](used_laptop_price_prediction.ipynb) | Main ML notebook | No (only if re-training) |
| **[best_model.pkl](best_model.pkl)** | **Trained Random Forest pipeline** | **YES — required** |
| **[model_metadata.json](model_metadata.json)** | **Feature names + metrics** | **YES — required** |

---

## Known Limitations

- **Small dataset (156 rows)** — limits model accuracy ceiling
- **Tokopedia-specific** — trained on one store, may not generalize to other marketplaces
- **Missing OS/display_type for ~50% of rows** — sellers often omit these in listings
- **Categorical features limited to brands seen during training** — passing an unseen brand will use one-hot's `handle_unknown='ignore'` (treated as all-zero vector)
- **No image-based features** — pure spec-based prediction
