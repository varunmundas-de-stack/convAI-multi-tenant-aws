"""
seed_realistic.py — 100k fact rows per tenant with authentic India FMCG data.

Sources used:
  - NielsenIQ India FMCG 2024: channel split (GT 75%, MT 10%, EC 8%)
  - Bizom / Delta Sales App: monthly seasonality indices
  - Blinkit / BigBasket / JioMart: live MRP verification per SKU
  - IMARC Group / Statista: state-wise FMCG market share
  - Storewise / Quora: PTD = ~76% of MRP; distributor margin 4–8%
  - ITC FY2024 results: MT+EC = 31% of ITC FMCG portfolio

Schema:
  fact_secondary_sales — one row per product line item in a distributor delivery
  invoice_value = qty × PTD_per_unit  (PTD = 76 % of MRP)
  discount is negotiated trade discount (3–12%)
  margin is distributor net margin after discount (4–10%)

Target: ~235 line-items/day × 425 days ≈ 100,000 rows per tenant
"""

import duckdb, random, math
from datetime import date, timedelta
from pathlib import Path

DB_PATH    = Path(__file__).parent / "cpg_multi_tenant.duckdb"
START_DATE = date(2025, 1, 1)
END_DATE   = date(2026, 2, 28)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1   # 425

TARGET_PER_TENANT = 100_000
BASE_DAILY = TARGET_PER_TENANT / TOTAL_DAYS      # ≈ 235.3

# ── Monthly seasonality (overall FMCG, base = 1.0) ───────────────────────────
# Source: Bizom seasonality study + Criteo Diwali 2024 report
MONTH_MULT = {
    1: 0.90,   # Jan — post-festive slowdown
    2: 0.88,   # Feb — low season
    3: 0.92,   # Mar — Holi / FY-end stocking
    4: 1.05,   # Apr — summer onset
    5: 1.10,   # May — peak summer
    6: 1.08,   # Jun — pre-monsoon trade loading
    7: 0.95,   # Jul — monsoon dip
    8: 1.00,   # Aug — Janmashtami / Ganesh mini-peak
    9: 1.05,   # Sep — Navratri pre-stocking
   10: 1.25,   # Oct — Navratri + Dussehra + Diwali (online +85%)
   11: 1.30,   # Nov — Diwali peak + wedding season
   12: 1.10,   # Dec — Christmas / New Year
}

# Day-of-week delivery pattern (Sunday = 0)
DOW_FACTOR = {0: 0.30, 1: 1.00, 2: 1.10, 3: 1.10, 4: 1.05, 5: 0.95, 6: 0.65}

# ── Geography — 15 cities with state-level FMCG market share weights ─────────
# Source: IMARC Group, Maximize Market Research, Statista regional reports
# Maharashtra 12%, UP 11%, Delhi 6%, Karnataka 7%, Tamil Nadu 6%, Gujarat 6%,
# West Bengal 5%, Rajasthan 4% of national FMCG
GEOGRAPHIES = [
    # key, state, district, town, geo_weight
    ( 1, "Maharashtra",   "Mumbai",       "Andheri West",      0.095),
    ( 2, "Maharashtra",   "Mumbai",       "Bandra West",       0.080),
    ( 3, "Maharashtra",   "Pune",         "Koregaon Park",     0.065),
    ( 4, "Maharashtra",   "Nagpur",       "Civil Lines",       0.030),
    ( 5, "Karnataka",     "Bengaluru",    "Koramangala",       0.075),
    ( 6, "Karnataka",     "Bengaluru",    "Whitefield",        0.060),
    ( 7, "Tamil Nadu",    "Chennai",      "T. Nagar",          0.075),
    ( 8, "Tamil Nadu",    "Chennai",      "Tambaram",          0.040),
    ( 9, "Delhi",         "New Delhi",    "Connaught Place",   0.080),
    (10, "Delhi",         "Gurgaon",      "DLF Phase 3",       0.060),
    (11, "Gujarat",       "Ahmedabad",    "Navrangpura",       0.065),
    (12, "Gujarat",       "Surat",        "Ring Road",         0.050),
    (13, "West Bengal",   "Kolkata",      "Park Street",       0.070),
    (14, "Uttar Pradesh", "Lucknow",      "Gomti Nagar",       0.055),
    (15, "Rajasthan",     "Jaipur",       "MI Road",           0.050),
]
GEO_WEIGHTS = [g[4] for g in GEOGRAPHIES]

# geo_key → hierarchy_key (aligned with 8-node hierarchy below)
GEO_HIER = {1:6, 2:6, 3:7, 4:7, 5:3, 6:3, 7:4, 8:4,
            9:1, 10:1, 11:8, 12:8, 13:5, 14:1, 15:2}

# Channels
CHANNELS = [(1,"GT"),(2,"MT"),(3,"E-Com"),(4,"IWS"),(5,"Pharma")]

# ── Category-level seasonal boost (multiplicative on top of MONTH_MULT) ──────
# Source: Bizom category seasonality, Criteo Diwali study
CAT_SEASON = {
    "Noodles":     {5:1.15, 6:1.15, 7:1.15, 8:1.10, 10:1.15, 11:1.15},
    "Condiments":  {10:1.20, 11:1.20},
    "Chocolate":   {10:1.40, 11:1.40, 12:1.20,  2:1.15},  # Diwali + Valentine
    "Coffee":      {11:1.15, 12:1.20,  1:1.15},           # winter hot bev
    "Dairy":       {10:1.20, 11:1.20},
    "Beverages":   { 4:1.30,  5:1.40,  6:1.30},           # peak summer
    "Home Care":   { 4:1.10,  5:1.10},                    # summer hygiene
    "Personal Care":{4:1.08,  5:1.08},
    "Biscuits":    {10:1.15, 11:1.15,  8:1.10},           # festive gifting
    "Snacks":      { 5:1.20,  6:1.15, 10:1.25, 11:1.20},
    "Staples":     {10:1.05, 11:1.05},
    "Stationery":  { 6:1.30,  7:1.30},                    # school season
}

# ── Quarterly trend index per (tenant, brand) to add realism ─────────────────
# Q1-2025, Q2-2025, Q3-2025, Q4-2025, Q1-2026 indices
BRAND_TREND = {
    # Nestle
    "Maggi":    [1.00, 1.02, 1.04, 1.06, 1.07],   # steady growth
    "KitKat":   [1.00, 0.98, 0.96, 0.97, 0.97],   # slight dip (competition)
    "Munch":    [1.00, 1.01, 1.02, 1.04, 1.05],
    "Nescafe":  [1.00, 1.05, 1.08, 1.12, 1.15],   # strong growth (WFH coffee)
    "Milkmaid": [1.00, 1.02, 1.03, 1.08, 1.08],   # festive gifting usage
    "Bar One":  [1.00, 0.99, 0.98, 1.01, 1.00],
    # HUL
    "Surf Excel":   [1.00, 1.02, 1.03, 1.05, 1.06],
    "Dove":         [1.00, 1.04, 1.07, 1.10, 1.12],  # premiumization trend
    "Lifebuoy":     [1.00, 0.98, 0.96, 0.95, 0.95],  # commoditization
    "Lux":          [1.00, 1.00, 0.99, 1.01, 1.01],
    "Brooke Bond":  [1.00, 1.01, 1.03, 1.06, 1.07],
    "Knorr":        [1.00, 1.03, 1.05, 1.08, 1.09],
    "Ponds":        [1.00, 1.02, 1.04, 1.06, 1.07],
    "Glow & Lovely":[1.00, 0.98, 0.97, 0.98, 0.98],  # rebranding pressure
    "Vim":          [1.00, 1.01, 1.02, 1.03, 1.04],
    # ITC
    "Aashirvaad": [1.00, 1.03, 1.05, 1.07, 1.08],  # brand #1 atta, growing
    "Sunfeast":   [1.00, 1.02, 1.04, 1.06, 1.07],
    "Bingo":      [1.00, 1.06, 1.11, 1.16, 1.20],  # fastest growing snack
    "Yippee":     [1.00, 1.04, 1.08, 1.12, 1.14],  # gaining on Maggi
    "Classmate":  [1.00, 1.00, 1.02, 1.03, 1.03],
}

def quarter_idx(d: date) -> int:
    """0-indexed quarter: Q1-2025=0 … Q1-2026=4"""
    if d.year == 2025:
        return (d.month - 1) // 3       # 0,1,2,3
    return 4                             # 2026 → index 4

# ── Tenant master data ────────────────────────────────────────────────────────
# Products: (sku_code, sku_name, brand, category, pack_size,
#            mrp_per_unit, ptd_per_unit, qty_min, qty_max, velocity, base_margin_pct)
# PTD ≈ 76% of MRP (national brand standard; source: Storewise)
# qty = units per invoice line (distributor order; carton-level)

TENANT_DATA = {

"nestle": {
  "products": [
    # Maggi — market leader instant noodles, MRP ₹14/70g (Hyperpure carton data)
    ("NGR-MAG001","Maggi 2-Min Masala Noodles", "Maggi","Noodles",    "70g",   14,  10.64,  480, 5760, 10, 5.5),
    ("NGR-MAG002","Maggi Noodles Family Pack",  "Maggi","Noodles",    "140g",  27,  20.52,  240, 2880,  8, 5.8),
    ("NGR-MAG003","Maggi Masala Tastemaker",    "Maggi","Condiments", "35g",   10,   7.60,  200, 2000,  5, 9.0),
    ("NGR-MAG004","Maggi Atta Noodles",         "Maggi","Noodles",    "70g",   15,  11.40,  400, 4800,  6, 5.5),
    ("NGR-MAG005","Maggi Tomato Ketchup",       "Maggi","Condiments", "500g",  80,  60.80,   24,  288,  5, 8.0),
    # KitKat — MRP ₹10 (mini), ₹30 (4F) verified Blinkit/Zepto
    ("NGR-KIT001","KitKat 2 Finger",            "KitKat","Chocolate", "18g",   10,   7.60,  240, 2880,  8, 8.5),
    ("NGR-KIT002","KitKat 4 Finger",            "KitKat","Chocolate", "37g",   30,  22.80,  120, 1440,  7, 8.0),
    ("NGR-KIT003","KitKat Chunky Bar",          "KitKat","Chocolate", "45g",   50,  38.00,   60,  720,  5, 8.5),
    ("NGR-MUN001","Munch Chocolate Bar",        "Munch","Chocolate",  "35g",   10,   7.60,  200, 2400,  7, 8.0),
    # Nescafe — MRP ₹230/50g jar, ₹910/200g jar (Blinkit verified)
    ("NGR-NES001","Nescafe Classic 50g Jar",    "Nescafe","Coffee",   "50g",  230, 174.80,   12,  144,  7,13.0),
    ("NGR-NES002","Nescafe Classic 200g Jar",   "Nescafe","Coffee",   "200g", 910, 691.60,    6,   72,  6,13.5),
    ("NGR-NES003","Nescafe Sunrise 200g",       "Nescafe","Coffee",   "200g", 750, 570.00,    6,   72,  5,12.5),
    ("NGR-NES004","Nescafe Gold Blend 50g",     "Nescafe","Coffee",   "50g",  399, 303.24,    6,   60,  4,16.0),
    # Milkmaid — MRP ~₹100/400g (BigBasket verified)
    ("NGR-MLK001","Milkmaid Condensed Milk",    "Milkmaid","Dairy",   "400g", 100,  76.00,   24,  288,  5, 7.5),
    ("NGR-BAR001","Bar One Chocolate Bar",      "Bar One","Chocolate","40g",   20,  15.20,  100, 1200,  5, 8.0),
  ],
  "customers": [
    # (key, distributor, retailer/outlet, outlet_type)  — channel weights: GT=75% MT=10% EC=8% IWS=4% Pharma=3%
    ( 1,"Suraj Enterprises",      "Kavita General Store",      "GT"),
    ( 2,"Metro Distributors",     "Big Bazaar",                "MT"),
    ( 3,"Sunrise Agencies",       "Amazon Pantry",             "E-Com"),
    ( 4,"Patel & Sons",           "Star Bazaar",               "MT"),
    ( 5,"Sharma Traders",         "Retailer's Choice Kirana",  "GT"),
    ( 6,"Verma Enterprises",      "DMart",                     "MT"),
    ( 7,"Royal Distributors",     "Flipkart Grocery",          "E-Com"),
    ( 8,"National Agency",        "Fresh2Home",                "E-Com"),
    ( 9,"Laxmi Trading Co",       "Kirana Corner",             "GT"),
    (10,"Balaji Suppliers",       "Spencer's Retail",          "MT"),
    (11,"Krishna Agencies",       "Nilgiris Supermarket",      "MT"),
    (12,"Om Distributors",        "Bazaar Point",              "GT"),
    (13,"Shanti Traders",         "Health & Glow Pharmacy",    "Pharma"),
    (14,"Anand Enterprises",      "Hospital Supply Co",        "IWS"),
    (15,"Trimurti Sales Corp",    "Park Avenue Kirana",        "GT"),
  ],
  # outlet_type → channel_key
  "hierarchy": [
    (1,"SO-N01","Deepak Sharma",    "ASM-N01","Raj Malhotra",   "ZSM-N","Vikram Singh",   "NSM-IN","Arun Kumar",   "North","North India"),
    (2,"SO-N02","Suresh Gupta",     "ASM-N01","Raj Malhotra",   "ZSM-N","Vikram Singh",   "NSM-IN","Arun Kumar",   "North","North India"),
    (3,"SO-S01","Karthik R",        "ASM-S01","Ramesh Nair",    "ZSM-S","Srinivas Rao",   "NSM-IN","Arun Kumar",   "South","South India"),
    (4,"SO-S02","Murugan K",        "ASM-S02","Ashok Kumar",    "ZSM-S","Srinivas Rao",   "NSM-IN","Arun Kumar",   "South","South India"),
    (5,"SO-E01","Sujit Das",        "ASM-E01","Biswas Roy",     "ZSM-E","Pranab Sen",     "NSM-IN","Arun Kumar",   "East", "East India"),
    (6,"SO-W01","Sachin Patil",     "ASM-W01","Sandeep Joshi",  "ZSM-W","Prashant Mehta", "NSM-IN","Arun Kumar",   "West", "West India"),
    (7,"SO-W02","Rohan Desai",      "ASM-W01","Sandeep Joshi",  "ZSM-W","Prashant Mehta", "NSM-IN","Arun Kumar",   "West", "West India"),
    (8,"SO-W03","Nilesh Shah",      "ASM-W02","Jigar Patel",    "ZSM-W","Prashant Mehta", "NSM-IN","Arun Kumar",   "West", "West India"),
  ],
},

"unilever": {
  "products": [
    # Surf Excel — MRP ₹90/500g, ₹175/1kg, ₹230/1kg QW (Zee Business / BigBasket)
    ("HUL-SUR001","Surf Excel Easy Wash 500g",       "Surf Excel","Home Care",    "500g",  90,  68.40,   48,  576, 10, 7.0),
    ("HUL-SUR002","Surf Excel Quick Wash 1kg",       "Surf Excel","Home Care",    "1kg",  230, 174.80,   24,  288,  9, 6.5),
    ("HUL-SUR003","Surf Excel Matic Front Load 1kg", "Surf Excel","Home Care",    "1kg",  220, 167.20,   24,  288,  7, 7.0),
    # Dove — MRP ₹40/75g soap, ₹245/180ml shampoo (HUL post-GST cut, Goodreturns)
    ("HUL-DOV001","Dove Moisturising Soap Bar",      "Dove","Personal Care",     "75g",   40,  30.40,  100, 1200,  8,12.0),
    ("HUL-DOV002","Dove Hair Fall Rescue Shampoo",   "Dove","Personal Care",     "180ml",245, 186.20,   12,  144,  7,13.5),
    ("HUL-DOV003","Dove Deeply Nourishing Body Wash","Dove","Personal Care",     "190ml",280, 212.80,   12,  120,  6,14.0),
    # Lifebuoy — MRP ~₹38/75g (post GST cut, Goodreturns)
    ("HUL-LIF001","Lifebuoy Total 10 Soap Bar",      "Lifebuoy","Personal Care", "75g",   38,  28.88,  120, 1440,  9, 9.0),
    ("HUL-LIF002","Lifebuoy Total Hand Wash 200ml",  "Lifebuoy","Personal Care", "200ml", 65,  49.40,   24,  288,  7,10.0),
    # Lux — MRP ~₹40/100g soap
    ("HUL-LUX001","Lux Soft Touch Soap Bar",         "Lux","Personal Care",      "75g",   38,  28.88,  100, 1200,  7, 9.5),
    # Brooke Bond — MRP ₹135/250g, ₹275/500g (BigBasket)
    ("HUL-BRK001","Brooke Bond Red Label Tea 250g",  "Brooke Bond","Beverages",  "250g", 135, 102.60,   24,  288,  8,11.0),
    ("HUL-BRK002","Brooke Bond Taj Mahal Tea 250g",  "Brooke Bond","Beverages",  "250g", 150, 114.00,   18,  216,  6,12.0),
    # Knorr — MRP ₹55/67g soup (Goodreturns post GST cut)
    ("HUL-KNR001","Knorr Classic Masala Noodles 65g","Knorr","Noodles",          "65g",   15,  11.40,  200, 2400,  6, 7.5),
    # Ponds — MRP ~₹90/73ml
    ("HUL-PON001","Ponds Light Moisturiser 73ml",    "Ponds","Personal Care",    "73ml",  90,  68.40,   24,  288,  6,14.0),
    # Glow & Lovely — MRP ~₹55/25g
    ("HUL-GLW001","Glow & Lovely Cream 25g",         "Glow & Lovely","Personal Care","25g", 55, 41.80, 48,  576,  6,15.0),
    # Vim — MRP ~₹30/155g bar
    ("HUL-VIM001","Vim Dishwash Bar 155g",           "Vim","Home Care",          "155g",  30,  22.80,  100, 1200,  8, 8.5),
  ],
  "customers": [
    ( 1,"Bharat Distributors",    "Reliance Fresh",            "MT"),
    ( 2,"Sapna Enterprises",      "BigBasket",                 "E-Com"),
    ( 3,"Surya Agencies",         "DMart",                     "MT"),
    ( 4,"Mahesh Traders",         "Blinkit",                   "E-Com"),
    ( 5,"United Distributors",    "Kirana King",               "GT"),
    ( 6,"Modern Trading Co",      "Star Bazaar",               "MT"),
    ( 7,"Shri Sai Agencies",      "Easyday Club",              "MT"),
    ( 8,"Pioneer Sales",          "Amazon Pantry",             "E-Com"),
    ( 9,"Raj Enterprises",        "Family Store",              "GT"),
    (10,"Eastern Agencies",       "HyperCity",                 "MT"),
    (11,"National Trading Co",    "Pharmacy Plus",             "Pharma"),
    (12,"Bright Distributors",    "Hotel & Hospitality Vendr", "IWS"),
    (13,"Annapurna Agencies",     "Meena Kirana Store",        "GT"),
    (14,"Fortune Traders",        "Nilgiris Supermarket",      "MT"),
    (15,"Bhagwan Suppliers",      "Corner Kirana",             "GT"),
  ],
  "hierarchy": [
    (1,"SO-N01","Amit Verma",       "ASM-N01","Rahul Srivastava","ZSM-N","Piyush Gupta",    "NSM-IN","Nisha Kapoor","North","North India"),
    (2,"SO-N02","Pankaj Misra",     "ASM-N01","Rahul Srivastava","ZSM-N","Piyush Gupta",    "NSM-IN","Nisha Kapoor","North","North India"),
    (3,"SO-S01","Ganesh Babu",      "ASM-S01","Venkat Raman",    "ZSM-S","Suresh Iyer",     "NSM-IN","Nisha Kapoor","South","South India"),
    (4,"SO-S02","Selva Kumar",      "ASM-S02","Mani Nathan",     "ZSM-S","Suresh Iyer",     "NSM-IN","Nisha Kapoor","South","South India"),
    (5,"SO-E01","Debashis Pal",     "ASM-E01","Soumya Ghosh",    "ZSM-E","Tapas Roy",       "NSM-IN","Nisha Kapoor","East", "East India"),
    (6,"SO-W01","Siddharth More",   "ASM-W01","Girish Kulkarni", "ZSM-W","Vilas Shinde",    "NSM-IN","Nisha Kapoor","West", "West India"),
    (7,"SO-W02","Akshay Deshpande", "ASM-W01","Girish Kulkarni", "ZSM-W","Vilas Shinde",    "NSM-IN","Nisha Kapoor","West", "West India"),
    (8,"SO-W03","Ravi Patel",       "ASM-W02","Harshad Shah",    "ZSM-W","Vilas Shinde",    "NSM-IN","Nisha Kapoor","West", "West India"),
  ],
},

"itc": {
  "products": [
    # Aashirvaad Atta — MRP ₹304/5kg (BigBasket verified), PTD ₹231
    ("ITC-ASH001","Aashirvaad Whole Wheat Atta 5kg",    "Aashirvaad","Staples",    "5kg",  304, 231.04,  10,  120, 10, 4.5),
    ("ITC-ASH002","Aashirvaad Select Sharbati Atta 5kg","Aashirvaad","Staples",    "5kg",  330, 250.80,   8,   96,  8, 4.8),
    ("ITC-ASH003","Aashirvaad Multigrain Atta 5kg",     "Aashirvaad","Staples",    "5kg",  310, 235.60,   6,   72,  6, 5.0),
    ("ITC-ASH004","Aashirvaad Iodised Salt 1kg",        "Aashirvaad","Condiments", "1kg",   25,  19.00,  100, 1200,  6, 8.0),
    # Sunfeast — MRP ₹30/Marie 200g, Bourbon Dark Fantasy ₹30/100g (Blinkit)
    ("ITC-SUN001","Sunfeast Marie Light Original 150g", "Sunfeast","Biscuits",     "150g",  30,  22.80,  100, 1200,  9, 8.5),
    ("ITC-SUN002","Sunfeast Glucose Gold 100g",         "Sunfeast","Biscuits",     "100g",  10,   7.60,  150, 1800,  8, 8.0),
    ("ITC-SUN003","Sunfeast Dark Fantasy Choco Fills",  "Sunfeast","Biscuits",     "75g",   30,  22.80,   80,  960,  7,10.5),
    ("ITC-SUN004","Sunfeast Dark Fantasy Vanilla",      "Sunfeast","Biscuits",     "75g",   30,  22.80,   80,  960,  6,10.5),
    ("ITC-SUN005","Sunfeast Farmlite Digestive 150g",   "Sunfeast","Biscuits",     "150g",  40,  30.40,   60,  720,  6,10.0),
    # Bingo — MRP ₹10/30g, ₹20/64g (Blinkit verified)
    ("ITC-BNG001","Bingo Mad Angles Achaari Masti 64g", "Bingo","Snacks",          "64g",   20,  15.20,  100, 1200,  9,11.0),
    ("ITC-BNG002","Bingo Tedhe Medhe Original 65g",     "Bingo","Snacks",          "65g",   20,  15.20,  100, 1200,  8,11.0),
    ("ITC-BNG003","Bingo Original Style Salted 52g",    "Bingo","Snacks",          "52g",   20,  15.20,   80, 1000,  7,11.0),
    # Yippee — MRP ₹15/70g (IndiaMart distributor quotes)
    ("ITC-YIP001","Yippee Magic Masala Noodles 70g",    "Yippee","Noodles",        "70g",   15,  11.40,  300, 3600,  8, 6.0),
    ("ITC-YIP002","Yippee Atta Noodles 70g",            "Yippee","Noodles",        "70g",   15,  11.40,  200, 2400,  6, 6.5),
    # Classmate — MRP ~₹60/notebook (stationery margin higher)
    ("ITC-CLS001","Classmate Notebook 160 Pages",       "Classmate","Stationery",  "1 pc",  65,  49.40,   50,  600,  5,14.0),
  ],
  "customers": [
    ( 1,"Annapurna Distributors", "Walmart India Best Price",  "MT"),
    ( 2,"Agro Agencies",          "Blinkit Warehouse",         "E-Com"),
    ( 3,"Mahadev Traders",        "Reliance Smart Bazaar",     "MT"),
    ( 4,"Vikram Enterprises",     "Swiggy Instamart Hub",      "E-Com"),
    ( 5,"Shree Distributors",     "Local Kirana Network",      "GT"),
    ( 6,"Delhi Fine Agencies",    "Zepto Dark Store",          "E-Com"),
    ( 7,"Jalaram Traders",        "Spencer's Retail",          "MT"),
    ( 8,"Bhavani Sales",          "Corner Grocery",            "GT"),
    ( 9,"Ganga Enterprises",      "Lulu Hypermarket",          "MT"),
    (10,"Sarvodaya Traders",      "HyperCity",                 "MT"),
    (11,"Ashoka Distributors",    "Medical & Pharmacy Store",  "Pharma"),
    (12,"New India Agency",       "Canteen Stores Dept",       "IWS"),
    (13,"Maa Vaishno Traders",    "Neighbourhood Outlet",      "GT"),
    (14,"Kesari Distributors",    "EasyMart Superstore",       "MT"),
    (15,"Arjun Sales Corp",       "FastMart Kirana",           "GT"),
  ],
  "hierarchy": [
    (1,"SO-N01","Rajesh Tiwari",   "ASM-N01","Sanjeev Saxena",  "ZSM-N","Ashish Dubey",   "NSM-IN","Mohan Reddy","North","North India"),
    (2,"SO-N02","Manoj Yadav",     "ASM-N01","Sanjeev Saxena",  "ZSM-N","Ashish Dubey",   "NSM-IN","Mohan Reddy","North","North India"),
    (3,"SO-S01","Satish Kumar",    "ASM-S01","Ravi Shankar",    "ZSM-S","Nagaraj S",      "NSM-IN","Mohan Reddy","South","South India"),
    (4,"SO-S02","Durai Murugan",   "ASM-S02","Velu Pillai",     "ZSM-S","Nagaraj S",      "NSM-IN","Mohan Reddy","South","South India"),
    (5,"SO-E01","Arnab Bose",      "ASM-E01","Subhro Majumdar", "ZSM-E","Partha Sarkar",  "NSM-IN","Mohan Reddy","East", "East India"),
    (6,"SO-W01","Vinayak Jadhav",  "ASM-W01","Dilip Kadam",     "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West", "West India"),
    (7,"SO-W02","Swapnil Gaikwad", "ASM-W01","Dilip Kadam",     "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West", "West India"),
    (8,"SO-W03","Chirag Modi",     "ASM-W02","Ketan Bhatt",     "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West", "West India"),
  ],
},

}  # end TENANT_DATA

OUTLET_TO_CHANNEL = {"GT": 1, "MT": 2, "E-Com": 3, "IWS": 4, "Pharma": 5}

# Customer selection weights by outlet type  (GT=75% MT=10% EC=8% IWS=4% Pharma=3%)
# Source: FieldAssist / NielsenIQ India channel split 2024
OUTLET_WEIGHT = {"GT": 75, "MT": 10, "E-Com": 8, "IWS": 4, "Pharma": 3}


def weighted_choice_idx(weights, rng):
    total = sum(weights)
    r = rng.random() * total
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if r < acc:
            return i
    return len(weights) - 1


def seed_tenant(conn, schema, data, seed_offset=0):
    client = schema.replace("client_", "")
    rng = random.Random(42 + seed_offset)
    print(f"\n[*] Seeding {schema} …", flush=True)

    # ── Drop & recreate ───────────────────────────────────────────────────────
    for tbl in ["fact_secondary_sales","dim_product","dim_geography",
                "dim_customer","dim_channel","dim_sales_hierarchy","dim_date"]:
        conn.execute(f"DROP TABLE IF EXISTS {schema}.{tbl}")

    conn.execute(f"""
        CREATE TABLE {schema}.dim_product (
            product_key INTEGER PRIMARY KEY, sku_code VARCHAR, sku_name VARCHAR,
            brand_name VARCHAR, category_name VARCHAR, pack_size VARCHAR
        )""")
    products = data["products"]
    for i, p in enumerate(products, 1):
        conn.execute(f"INSERT INTO {schema}.dim_product VALUES (?,?,?,?,?,?)",
                     [i, p[0], p[1], p[2], p[3], p[4]])

    conn.execute(f"""
        CREATE TABLE {schema}.dim_geography (
            geography_key INTEGER PRIMARY KEY, state_name VARCHAR,
            district_name VARCHAR, town_name VARCHAR
        )""")
    for g in GEOGRAPHIES:
        conn.execute(f"INSERT INTO {schema}.dim_geography VALUES (?,?,?,?)", list(g[:4]))

    conn.execute(f"""
        CREATE TABLE {schema}.dim_customer (
            customer_key INTEGER PRIMARY KEY, distributor_name VARCHAR,
            retailer_name VARCHAR, outlet_type VARCHAR
        )""")
    customers = data["customers"]
    for c in customers:
        conn.execute(f"INSERT INTO {schema}.dim_customer VALUES (?,?,?,?)", list(c))

    conn.execute(f"""
        CREATE TABLE {schema}.dim_channel (
            channel_key INTEGER PRIMARY KEY, channel_name VARCHAR
        )""")
    for ch in CHANNELS:
        conn.execute(f"INSERT INTO {schema}.dim_channel VALUES (?,?)", list(ch))

    conn.execute(f"""
        CREATE TABLE {schema}.dim_sales_hierarchy (
            hierarchy_key INTEGER PRIMARY KEY,
            so_code VARCHAR, so_name VARCHAR, asm_code VARCHAR, asm_name VARCHAR,
            zsm_code VARCHAR, zsm_name VARCHAR, nsm_code VARCHAR, nsm_name VARCHAR,
            zone_name VARCHAR, region_name VARCHAR
        )""")
    for row in data["hierarchy"]:
        conn.execute(f"INSERT INTO {schema}.dim_sales_hierarchy VALUES (?,?,?,?,?,?,?,?,?,?,?)", list(row))

    conn.execute(f"""
        CREATE TABLE {schema}.dim_date (
            date_key INTEGER PRIMARY KEY, date DATE,
            year INTEGER, quarter INTEGER, month INTEGER,
            month_name VARCHAR, week INTEGER
        )""")
    d = START_DATE
    while d <= END_DATE:
        dk = (d - START_DATE).days + 1
        conn.execute(f"INSERT INTO {schema}.dim_date VALUES (?,?,?,?,?,?,?)", [
            dk, d.isoformat(), d.year, (d.month-1)//3+1, d.month,
            d.strftime("%B"), d.isocalendar()[1]
        ])
        d += timedelta(days=1)

    conn.execute(f"""
        CREATE TABLE {schema}.fact_secondary_sales (
            invoice_key INTEGER PRIMARY KEY,
            invoice_date DATE, product_key INTEGER, geography_key INTEGER,
            customer_key INTEGER, channel_key INTEGER, date_key INTEGER,
            sales_hierarchy_key INTEGER, invoice_number VARCHAR,
            invoice_value DECIMAL(12,2), discount_amount DECIMAL(12,2),
            discount_percentage DECIMAL(5,2), net_value DECIMAL(12,2),
            invoice_quantity INTEGER, margin_amount DECIMAL(12,2),
            margin_percentage DECIMAL(5,2), return_flag BOOLEAN DEFAULT FALSE
        )""")

    # ── Precompute per-product velocity & customer weights ────────────────────
    n_prod     = len(products)
    velocities = [p[9] for p in products]

    # Customer weights: proportional to channel share
    cust_weights = [OUTLET_WEIGHT[c[3]] / sum(
        1 for cc in customers if cc[3] == c[3]
    ) for c in customers]

    # ── Fact generation ───────────────────────────────────────────────────────
    rows_buffer = []
    invoice_key = 1
    d = START_DATE

    while d <= END_DATE:
        dk = (d - START_DATE).days + 1
        month_m  = MONTH_MULT[d.month]
        dow_m    = DOW_FACTOR[d.weekday()]

        # Compute daily target and add Gaussian noise
        daily_target = BASE_DAILY * month_m * dow_m
        n_invoices   = max(1, round(rng.gauss(daily_target, daily_target * 0.12)))

        for _ in range(n_invoices):
            # ── Pick product (velocity-weighted) ─────────────────────────────
            p_idx = weighted_choice_idx(velocities, rng)
            p     = products[p_idx]
            pk    = p_idx + 1
            brand, category = p[2], p[3]
            ptd_unit        = p[6]
            qty_min, qty_max= p[7], p[8]
            base_margin     = p[10]

            # Category × month seasonal boost
            cat_boost = CAT_SEASON.get(category, {}).get(d.month, 1.0)

            # Brand quarterly trend (realism: Nescafe growing, KitKat dipping, etc.)
            trend = BRAND_TREND.get(brand, [1.0]*5)
            q_idx = quarter_idx(d)
            brand_mult = trend[min(q_idx, len(trend)-1)]

            # Adjust max quantity by seasonal + trend
            adj_max = max(qty_min + 1, int(qty_max * cat_boost * brand_mult))
            adj_min = qty_min

            # ── Pick geography (state-market-share weighted) ──────────────────
            g_idx = weighted_choice_idx(GEO_WEIGHTS, rng)
            geo_key  = GEOGRAPHIES[g_idx][0]
            hier_key = GEO_HIER[geo_key]

            # ── Pick customer (channel-share weighted) ────────────────────────
            c_idx    = weighted_choice_idx(cust_weights, rng)
            cust     = customers[c_idx]
            cust_key = cust[0]
            chan_key = OUTLET_TO_CHANNEL[cust[3]]

            # ── Compute invoice ───────────────────────────────────────────────
            qty      = rng.randint(adj_min, adj_max)
            inv_val  = round(qty * ptd_unit, 2)

            disc_pct = round(rng.uniform(3.0, 12.0), 2)
            disc_amt = round(inv_val * disc_pct / 100, 2)
            net_val  = round(inv_val - disc_amt, 2)

            margin_pct = round(max(3.0, min(18.0, rng.gauss(base_margin, 1.5))), 2)
            margin_amt = round(net_val * margin_pct / 100, 2)

            ret_flag = rng.random() < 0.018   # ~1.8% return rate

            rows_buffer.append([
                invoice_key, d.isoformat(), pk, geo_key, cust_key, chan_key,
                dk, hier_key,
                f"INV{invoice_key:06d}-{client}",
                inv_val, disc_amt, disc_pct, net_val,
                qty, margin_amt, margin_pct, ret_flag
            ])
            invoice_key += 1

            # Batch insert every 5000 rows to keep memory low
            if len(rows_buffer) >= 5000:
                conn.executemany(
                    f"INSERT INTO {schema}.fact_secondary_sales VALUES "
                    f"(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows_buffer
                )
                rows_buffer.clear()

        d += timedelta(days=1)

    # Flush remainder
    if rows_buffer:
        conn.executemany(
            f"INSERT INTO {schema}.fact_secondary_sales VALUES "
            f"(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows_buffer
        )

    fact_count = conn.execute(
        f"SELECT COUNT(*) FROM {schema}.fact_secondary_sales"
    ).fetchone()[0]
    total_val = conn.execute(
        f"SELECT ROUND(SUM(net_value)/1e7,2) FROM {schema}.fact_secondary_sales"
    ).fetchone()[0]
    print(f"    ✓ {fact_count:,} rows  |  net GMV ₹{total_val} Cr  "
          f"|  {START_DATE} → {END_DATE}", flush=True)


def main():
    print(f"DB: {DB_PATH}")
    conn = duckdb.connect(str(DB_PATH))

    for i, (tenant, data) in enumerate(TENANT_DATA.items()):
        schema = f"client_{tenant}"
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        seed_tenant(conn, schema, data, seed_offset=i * 100)

    conn.close()
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n✓  All done — DB size: {size_mb:.1f} MB")
    print(f"   Open http://<EC2-IP> and ask: "
          f"\"Top 5 brands by net sales in Q4 2025\"")


if __name__ == "__main__":
    main()
