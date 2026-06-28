# Used Laptop Price Predictor — AOL Machine Learning

**Group Members:**
- 2802392816 — Billie Godwin
- 2802393030 — Demetrius Denzell Tan
- 2802394456 — Ariya Saddhana Lius

---

## Project Overview

A machine learning regression system that predicts the market price of used laptops based on their hardware specifications. Data was scraped directly from a real Tokopedia store ([Specialist Laptop Second](https://www.tokopedia.com/specialistlaptop/product/)), giving the model real Indonesian market pricing.

---

## Project Structure

```
AOL ML/
├── README.md                                  ← This file
├── Proposal ML.pdf                            ← Original project proposal
│
├── Data Pipeline
│   ├── scraper.py                             ← Scrapes all product pages from Tokopedia
│   ├── rescrape_parallel.py                   ← Re-scrapes failed rows (4 parallel workers)
│   ├── clean_data.py                          ← Cleans & normalizes raw scraped data
│   ├── laptops_raw.csv                        ← Raw scraped data (301 rows)
│   └── laptops_clean.csv                      ← Clean dataset for ML (156 rows, 19 cols)
│
├── Machine Learning
│   ├── used_laptop_price_prediction.ipynb     ← Main notebook (EDA + training + backtesting)
│   ├── best_model.pkl                         ← Saved best model pipeline (Random Forest)
│   └── model_metadata.json                    ← Model metrics, features, hyperparameters
│
└── Deployment
    ├── app.py                                 ← Streamlit web app
    └── requirements.txt                       ← Python dependencies
```

---

## Dataset

- **Source:** [Specialist Laptop Second — Tokopedia](https://www.tokopedia.com/specialistlaptop/product/)
- **Raw:** 301 scraped listings
- **Clean:** 156 used laptop rows after filtering non-laptops (chargers, desktops, RAM modules)
- **Target:** `price_idr` (Rp 990,000 – Rp 14,000,000)

### Key Features Used for Modeling

| Feature | Description |
|---|---|
| `brand` | Manufacturer (Lenovo, Dell, HP, etc.) |
| `cpu_tier` | CPU class (i5, i7, ryzen, other) |
| `cpu_gen` | CPU generation number (1–12) |
| `ram_gb` | RAM in GB |
| `ssd_gb` | SSD storage in GB |
| `nvme` | NVMe SSD (0/1) |
| `screen_inch` | Screen size |
| `is_fhd` | Full HD display (0/1) |
| `is_ips` | IPS panel (0/1) |
| `touchscreen` | Touchscreen (0/1) |
| `gpu_type_bin` | Dedicated GPU (0/1) |
| `storage_type_bin` | SSD vs HDD (0/1) |
| `sold_count_log` | log(1 + units sold) |
| `rating` | Seller rating (1–5) |
| `has_os_label` | Seller listed an OS (0/1) |

---

## Models & Results

| Model | MAE | RMSE | R² |
|---|---|---|---|
| Linear Regression (Baseline) | see notebook | see notebook | see notebook |
| **Random Forest (Tuned)** | **Rp 686,669** | **Rp 1,091,164** | **0.645** |
| SVR (Tuned) | see notebook | see notebook | see notebook |

**Best model:** Random Forest (`n_estimators=200, max_depth=10, min_samples_leaf=2`)

The full comparison table with all three models is in the notebook — Section 8.

**Practical accuracy:** Predictions are within ~Rp 687k on average (~17% of the Rp 4M median price).

---

## How to Run

### 1. Reproduce the full data pipeline (optional — data already provided)
```bash
python scraper.py             # scrape raw data → laptops_raw.csv
python rescrape_parallel.py   # retry failed rows
python clean_data.py          # clean → laptops_clean.csv
```

### 2. Run the ML notebook
Open `used_laptop_price_prediction.ipynb` in Jupyter / VS Code and run all cells, or:
```bash
python -m jupyter nbconvert --to notebook --execute --inplace used_laptop_price_prediction.ipynb
```

### 3. Run the Streamlit app
```bash
pip install -r requirements.txt
streamlit run app.py
```
Then open http://localhost:8501 in your browser.

Or use this streamlit link:
https://used-laptop-price-predictor-g9gaykv4menkrwfrm2wwfe.streamlit.app/

---

## Dependencies

```
Python 3.12+
selenium==4.44.0
beautifulsoup4==4.14.3
scikit-learn==1.8.0
pandas
numpy
matplotlib
seaborn
joblib
jupyter / nbconvert
streamlit                  # for the web app (Step 5)
```
