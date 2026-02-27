"""
seed_realistic.py — Replace synthetic CPG data with realistic brand/SKU data.

Per tenant:
  - 15 real SKUs (Maggi/KitKat/Nescafe | Surf Excel/Dove/Brooke Bond | Aashirvaad/Bingo/Yippee)
  - 15 geographies across India
  - 15 named distributors / outlet chains
  - 8 sales hierarchy nodes (NSM → ZSM → ASM → SO)
  - ~3,000 fact rows over 14 months (Jan 2025 – Feb 2026)
  - Seasonal patterns: Diwali +50%, summer +25%, monsoon −15%

Run with:
  python3 database/seed_realistic.py
"""
import duckdb, random
from datetime import date, timedelta
from pathlib import Path

DB_PATH    = Path(__file__).parent / "cpg_multi_tenant.duckdb"
START_DATE = date(2025, 1, 1)
END_DATE   = date(2026, 2, 28)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1  # 425

# Monthly seasonality multiplier (India FMCG calendar)
MONTH_MULT = {
    1: 1.00,  # Jan — post-festive normalisation
    2: 0.95,  # Feb
    3: 1.10,  # Mar — summer begins
    4: 1.20,  # Apr — peak summer
    5: 1.25,  # May — peak summer
    6: 1.10,  # Jun — pre-monsoon trade loading
    7: 0.85,  # Jul — monsoon dip
    8: 0.90,  # Aug — monsoon
    9: 0.95,  # Sep — end of monsoon
   10: 1.50,  # Oct — Diwali / festive peak
   11: 1.30,  # Nov — post-Diwali + winter
   12: 1.20,  # Dec — year-end push
}

# ─── Shared geography (same 15 cities for all tenants) ───────────────────────
GEOGRAPHIES = [
    (1,  "Maharashtra",   "Mumbai",       "Andheri West"),
    (2,  "Maharashtra",   "Mumbai",       "Bandra West"),
    (3,  "Maharashtra",   "Pune",         "Koregaon Park"),
    (4,  "Maharashtra",   "Nagpur",       "Civil Lines"),
    (5,  "Karnataka",     "Bengaluru",    "Koramangala"),
    (6,  "Karnataka",     "Bengaluru",    "Whitefield"),
    (7,  "Tamil Nadu",    "Chennai",      "T. Nagar"),
    (8,  "Tamil Nadu",    "Chennai",      "Tambaram"),
    (9,  "Delhi",         "New Delhi",    "Connaught Place"),
    (10, "Delhi",         "Gurgaon",      "DLF Phase 3"),
    (11, "Gujarat",       "Ahmedabad",    "Navrangpura"),
    (12, "Gujarat",       "Surat",        "Ring Road"),
    (13, "West Bengal",   "Kolkata",      "Park Street"),
    (14, "Uttar Pradesh", "Lucknow",      "Gomti Nagar"),
    (15, "Rajasthan",     "Jaipur",       "MI Road"),
]

# geo_key → hierarchy_key mapping
GEO_HIER = {1:6, 2:6, 3:7, 4:7, 5:3, 6:3, 7:4, 8:4,
            9:1, 10:1, 11:8, 12:8, 13:5, 14:1, 15:2}

# Shared channels
CHANNELS = [(1,"GT"),(2,"MT"),(3,"E-Com"),(4,"IWS"),(5,"Pharma")]

# ─── Tenant-specific master data ─────────────────────────────────────────────
TENANT_DATA = {

"nestle": {
  "products": [
    # sku_code, sku_name, brand, category, pack_size, val_min, val_max, velocity, margin_pct
    ("NGR-MAG001","Maggi 2-Min Noodles",       "Maggi",   "Noodles",    "70g",    6000, 45000, 10, 14),
    ("NGR-MAG002","Maggi Noodles Family Pack",  "Maggi",   "Noodles",    "140g",   8000, 60000,  8, 13),
    ("NGR-MAG003","Maggi Masala Powder",        "Maggi",   "Condiments", "35g",    3000, 20000,  5, 18),
    ("NGR-MAG004","Maggi Atta Noodles",         "Maggi",   "Noodles",    "70g",    5500, 40000,  6, 15),
    ("NGR-MAG005","Maggi Tomato Ketchup",       "Maggi",   "Condiments", "500g",   7000, 50000,  5, 20),
    ("NGR-KIT001","KitKat 2 Finger",            "KitKat",  "Chocolate",  "18g",    4000, 30000,  8, 22),
    ("NGR-KIT002","KitKat 4 Finger",            "KitKat",  "Chocolate",  "37g",    6000, 45000,  7, 21),
    ("NGR-KIT003","KitKat Chunky",              "KitKat",  "Chocolate",  "45g",    5000, 38000,  5, 22),
    ("NGR-MUN001","Munch Chocolate Bar",        "Munch",   "Chocolate",  "35g",    3500, 25000,  7, 20),
    ("NGR-NES001","Nescafe Classic 50g",        "Nescafe", "Coffee",     "50g",    8000, 60000,  7, 28),
    ("NGR-NES002","Nescafe Classic 200g",       "Nescafe", "Coffee",     "200g",  15000, 90000,  6, 27),
    ("NGR-NES003","Nescafe Sunrise 200g",       "Nescafe", "Coffee",     "200g",  12000, 80000,  5, 25),
    ("NGR-NES004","Nescafe Gold 100g",          "Nescafe", "Coffee",     "100g",  20000,120000,  4, 32),
    ("NGR-MLK001","Milkmaid Condensed Milk",    "Milkmaid","Dairy",      "400g",  10000, 70000,  5, 18),
    ("NGR-BAR001","Bar One Chocolate",          "Bar One", "Chocolate",  "40g",    3000, 22000,  5, 21),
  ],
  "customers": [
    (1, "Suraj Enterprises",     "Kavita General Store",    "GT"),
    (2, "Metro Distributors",    "Big Bazaar",              "MT"),
    (3, "Sunrise Agencies",      "Amazon Pantry",           "E-Com"),
    (4, "Patel & Sons",          "Star Bazaar",             "MT"),
    (5, "Sharma Traders",        "Retailers Choice",        "GT"),
    (6, "Verma Enterprises",     "DMart",                   "MT"),
    (7, "Royal Distributors",    "Flipkart Grocery",        "E-Com"),
    (8, "National Agency",       "Fresh2Home",              "E-Com"),
    (9, "Laxmi Trading Co",      "Kirana Corner",           "GT"),
    (10,"Balaji Suppliers",      "Spencer's Retail",        "MT"),
    (11,"Krishna Agencies",      "Nilgiris Supermarket",    "MT"),
    (12,"Om Distributors",       "Bazaar Point",            "GT"),
    (13,"Shanti Traders",        "Health & Glow",           "Pharma"),
    (14,"Anand Enterprises",     "Hospital Supply Co",      "IWS"),
    (15,"Trimurti Sales Corp",   "Park Avenue Store",       "GT"),
  ],
  "hierarchy": [
    (1,"SO-N01","Deepak Sharma",   "ASM-N01","Raj Malhotra",  "ZSM-N","Vikram Singh",  "NSM-IN","Arun Kumar","North","North India"),
    (2,"SO-N02","Suresh Gupta",    "ASM-N01","Raj Malhotra",  "ZSM-N","Vikram Singh",  "NSM-IN","Arun Kumar","North","North India"),
    (3,"SO-S01","Karthik R",       "ASM-S01","Ramesh Nair",   "ZSM-S","Srinivas Rao",  "NSM-IN","Arun Kumar","South","South India"),
    (4,"SO-S02","Murugan K",       "ASM-S02","Ashok Kumar",   "ZSM-S","Srinivas Rao",  "NSM-IN","Arun Kumar","South","South India"),
    (5,"SO-E01","Sujit Das",       "ASM-E01","Biswas Roy",    "ZSM-E","Pranab Sen",    "NSM-IN","Arun Kumar","East","East India"),
    (6,"SO-W01","Sachin Patil",    "ASM-W01","Sandeep Joshi", "ZSM-W","Prashant Mehta","NSM-IN","Arun Kumar","West","West India"),
    (7,"SO-W02","Rohan Desai",     "ASM-W01","Sandeep Joshi", "ZSM-W","Prashant Mehta","NSM-IN","Arun Kumar","West","West India"),
    (8,"SO-W03","Nilesh Shah",     "ASM-W02","Jigar Patel",   "ZSM-W","Prashant Mehta","NSM-IN","Arun Kumar","West","West India"),
  ],
},

"unilever": {
  "products": [
    ("HUL-SUR001","Surf Excel Easy Wash",       "Surf Excel","Home Care",    "500g",  10000, 70000, 10, 16),
    ("HUL-SUR002","Surf Excel Quick Wash",      "Surf Excel","Home Care",    "1kg",   18000,120000,  9, 15),
    ("HUL-SUR003","Surf Excel Matic Front Load","Surf Excel","Home Care",    "1kg",   20000,130000,  7, 16),
    ("HUL-DOV001","Dove Soap Moisturising",     "Dove",      "Personal Care","75g",    4000, 30000,  8, 25),
    ("HUL-DOV002","Dove Shampoo",               "Dove",      "Personal Care","180ml",  8000, 55000,  7, 28),
    ("HUL-DOV003","Dove Body Wash",             "Dove",      "Personal Care","200ml",  9000, 60000,  6, 27),
    ("HUL-LIF001","Lifebuoy Total 10 Soap",     "Lifebuoy",  "Personal Care","75g",    3500, 25000,  9, 20),
    ("HUL-LIF002","Lifebuoy Hand Wash",         "Lifebuoy",  "Personal Care","200ml",  6000, 42000,  7, 22),
    ("HUL-LUX001","Lux Soft Touch Soap",        "Lux",       "Personal Care","75g",    3500, 25000,  7, 22),
    ("HUL-BRK001","Brooke Bond Red Label Tea",  "Brooke Bond","Beverages",   "250g",  10000, 72000,  8, 24),
    ("HUL-BRK002","Brooke Bond Taj Mahal Tea",  "Brooke Bond","Beverages",   "250g",  12000, 80000,  6, 26),
    ("HUL-KNR001","Knorr Chicken Noodles",      "Knorr",     "Noodles",      "70g",    5000, 36000,  6, 18),
    ("HUL-PON001","Ponds Light Moisturiser",    "Ponds",     "Personal Care","73ml",   7000, 48000,  6, 30),
    ("HUL-GLW001","Glow & Lovely Face Cream",   "Glow & Lovely","Personal Care","25g", 5000, 36000,  6, 32),
    ("HUL-VIM001","Vim Dishwash Bar",           "Vim",       "Home Care",    "155g",   4000, 28000,  8, 18),
  ],
  "customers": [
    (1, "Bharat Distributors",   "Reliance Fresh",          "MT"),
    (2, "Sapna Enterprises",     "BigBasket",               "E-Com"),
    (3, "Surya Agencies",        "DMart",                   "MT"),
    (4, "Mahesh Traders",        "Grofers / Blinkit",       "E-Com"),
    (5, "United Distributors",   "Kirana King",             "GT"),
    (6, "Modern Trading Co",     "Star Bazaar",             "MT"),
    (7, "Shri Sai Agencies",     "Easyday Club",            "MT"),
    (8, "Pioneer Sales",         "Amazon Pantry",           "E-Com"),
    (9, "Raj Enterprises",       "Family Store",            "GT"),
    (10,"Eastern Agencies",      "HyperCity",               "MT"),
    (11,"National Trading Co",   "Pharmacy Plus",           "Pharma"),
    (12,"Bright Distributors",   "Hotel & Hospitality",     "IWS"),
    (13,"Annapurna Agencies",    "Meena Kirana",            "GT"),
    (14,"Fortune Traders",       "Nilgiris Supermarket",    "MT"),
    (15,"Bhagwan Suppliers",     "Corner Shop",             "GT"),
  ],
  "hierarchy": [
    (1,"SO-N01","Amit Verma",      "ASM-N01","Rahul Srivastava","ZSM-N","Piyush Gupta",   "NSM-IN","Nisha Kapoor","North","North India"),
    (2,"SO-N02","Pankaj Misra",    "ASM-N01","Rahul Srivastava","ZSM-N","Piyush Gupta",   "NSM-IN","Nisha Kapoor","North","North India"),
    (3,"SO-S01","Ganesh Babu",     "ASM-S01","Venkat Raman",    "ZSM-S","Suresh Iyer",    "NSM-IN","Nisha Kapoor","South","South India"),
    (4,"SO-S02","Selva Kumar",     "ASM-S02","Mani Nathan",     "ZSM-S","Suresh Iyer",    "NSM-IN","Nisha Kapoor","South","South India"),
    (5,"SO-E01","Debashis Pal",    "ASM-E01","Soumya Ghosh",    "ZSM-E","Tapas Roy",      "NSM-IN","Nisha Kapoor","East","East India"),
    (6,"SO-W01","Siddharth More",  "ASM-W01","Girish Kulkarni", "ZSM-W","Vilas Shinde",   "NSM-IN","Nisha Kapoor","West","West India"),
    (7,"SO-W02","Akshay Deshpande","ASM-W01","Girish Kulkarni", "ZSM-W","Vilas Shinde",   "NSM-IN","Nisha Kapoor","West","West India"),
    (8,"SO-W03","Ravi Patel",      "ASM-W02","Harshad Shah",    "ZSM-W","Vilas Shinde",   "NSM-IN","Nisha Kapoor","West","West India"),
  ],
},

"itc": {
  "products": [
    ("ITC-ASH001","Aashirvaad Whole Wheat Atta",    "Aashirvaad","Staples",    "5kg",   25000,180000, 10, 10),
    ("ITC-ASH002","Aashirvaad Select Sharbati Atta","Aashirvaad","Staples",    "5kg",   28000,200000,  8, 11),
    ("ITC-ASH003","Aashirvaad Multigrain Atta",     "Aashirvaad","Staples",    "5kg",   26000,190000,  6, 12),
    ("ITC-ASH004","Aashirvaad Salt",                "Aashirvaad","Condiments", "1kg",    4000, 28000,  6, 15),
    ("ITC-SUN001","Sunfeast Marie Light Original",  "Sunfeast",  "Biscuits",   "150g",   5000, 36000,  9, 18),
    ("ITC-SUN002","Sunfeast Glucose Biscuit",       "Sunfeast",  "Biscuits",   "120g",   4000, 28000,  8, 17),
    ("ITC-SUN003","Sunfeast Dark Fantasy Choco",    "Sunfeast",  "Biscuits",   "75g",    6000, 42000,  7, 22),
    ("ITC-SUN004","Sunfeast Dark Fantasy Vanilla",  "Sunfeast",  "Biscuits",   "75g",    5500, 40000,  6, 22),
    ("ITC-SUN005","Sunfeast Mom's Magic",           "Sunfeast",  "Biscuits",   "200g",   6000, 44000,  6, 20),
    ("ITC-BNG001","Bingo Mad Angles Achaari",       "Bingo",     "Snacks",     "35g",    3500, 25000,  9, 24),
    ("ITC-BNG002","Bingo Tedhe Medhe Original",     "Bingo",     "Snacks",     "65g",    5000, 35000,  8, 23),
    ("ITC-BNG003","Bingo Original Style Salted",    "Bingo",     "Snacks",     "52g",    4000, 28000,  7, 22),
    ("ITC-YIP001","Yippee Magic Masala Noodles",    "Yippee",    "Noodles",    "70g",    5500, 40000,  8, 17),
    ("ITC-YIP002","Yippee Atta Noodles",            "Yippee",    "Noodles",    "70g",    5000, 36000,  6, 18),
    ("ITC-CLS001","Classmate Notebook 160pg",       "Classmate", "Stationery", "1 pc",   8000, 55000,  5, 30),
  ],
  "customers": [
    (1, "Annapurna Distributors", "Walmart India",           "MT"),
    (2, "Agro Agencies",          "Blinkit",                 "E-Com"),
    (3, "Mahadev Traders",        "Reliance Smart",          "MT"),
    (4, "Vikram Enterprises",     "Swiggy Instamart",        "E-Com"),
    (5, "Shree Distributors",     "Local Kirana",            "GT"),
    (6, "Delhi Fine Agencies",    "Zepto",                   "E-Com"),
    (7, "Jalaram Traders",        "Spencer's",               "MT"),
    (8, "Bhavani Sales",          "Corner Grocery",          "GT"),
    (9, "Ganga Enterprises",      "Lulu Hypermarket",        "MT"),
    (10,"Sarvodaya Traders",      "HyperCity",               "MT"),
    (11,"Ashoka Distributors",    "Medical Shop",            "Pharma"),
    (12,"New India Agency",       "Canteen Store Dept",      "IWS"),
    (13,"Maa Vaishno Traders",    "Local Outlet",            "GT"),
    (14,"Kesari Distributors",    "EasyMart",                "MT"),
    (15,"Arjun Sales Corp",       "FastMart",                "GT"),
  ],
  "hierarchy": [
    (1,"SO-N01","Rajesh Tiwari",  "ASM-N01","Sanjeev Saxena", "ZSM-N","Ashish Dubey",  "NSM-IN","Mohan Reddy","North","North India"),
    (2,"SO-N02","Manoj Yadav",    "ASM-N01","Sanjeev Saxena", "ZSM-N","Ashish Dubey",  "NSM-IN","Mohan Reddy","North","North India"),
    (3,"SO-S01","Satish Kumar",   "ASM-S01","Ravi Shankar",   "ZSM-S","Nagaraj S",     "NSM-IN","Mohan Reddy","South","South India"),
    (4,"SO-S02","Durai Murugan",  "ASM-S02","Velu Pillai",    "ZSM-S","Nagaraj S",     "NSM-IN","Mohan Reddy","South","South India"),
    (5,"SO-E01","Arnab Bose",     "ASM-E01","Subhro Majumdar","ZSM-E","Partha Sarkar", "NSM-IN","Mohan Reddy","East","East India"),
    (6,"SO-W01","Vinayak Jadhav", "ASM-W01","Dilip Kadam",    "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West","West India"),
    (7,"SO-W02","Swapnil Gaikwad","ASM-W01","Dilip Kadam",    "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West","West India"),
    (8,"SO-W03","Chirag Modi",    "ASM-W02","Ketan Bhatt",    "ZSM-W","Sudhir Kulkarni","NSM-IN","Mohan Reddy","West","West India"),
  ],
},

}  # end TENANT_DATA


# ─── Helpers ──────────────────────────────────────────────────────────────────

def date_key(d):
    """Return date_key (1-based offset from START_DATE)."""
    return (d - START_DATE).days + 1


def weighted_choice(items, weights):
    total = sum(weights)
    r = random.random() * total
    acc = 0
    for item, w in zip(items, weights):
        acc += w
        if r < acc:
            return item
    return items[-1]


# ─── Channel weights by customer outlet type ─────────────────────────────────
CHANNEL_BY_OUTLET = {"GT": 1, "MT": 2, "E-Com": 3, "IWS": 4, "Pharma": 5}


# ─── Main seeder ──────────────────────────────────────────────────────────────

def seed_tenant(conn, schema, data, seed_offset=0):
    client = schema.replace("client_", "")
    rng = random.Random(42 + seed_offset)
    print(f"\n[*] Seeding {schema} …")

    # Drop and recreate tables
    conn.execute(f"DROP TABLE IF EXISTS {schema}.fact_secondary_sales")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_product")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_geography")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_customer")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_channel")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_sales_hierarchy")
    conn.execute(f"DROP TABLE IF EXISTS {schema}.dim_date")

    # dim_product
    conn.execute(f"""
        CREATE TABLE {schema}.dim_product (
            product_key INTEGER PRIMARY KEY, sku_code VARCHAR, sku_name VARCHAR,
            brand_name VARCHAR, category_name VARCHAR, pack_size VARCHAR
        )""")
    for i, (sku, name, brand, cat, pack, *_) in enumerate(data["products"], 1):
        conn.execute(f"INSERT INTO {schema}.dim_product VALUES (?,?,?,?,?,?)",
                     [i, sku, name, brand, cat, pack])

    # dim_geography
    conn.execute(f"""
        CREATE TABLE {schema}.dim_geography (
            geography_key INTEGER PRIMARY KEY, state_name VARCHAR,
            district_name VARCHAR, town_name VARCHAR
        )""")
    for row in GEOGRAPHIES:
        conn.execute(f"INSERT INTO {schema}.dim_geography VALUES (?,?,?,?)", list(row))

    # dim_customer
    conn.execute(f"""
        CREATE TABLE {schema}.dim_customer (
            customer_key INTEGER PRIMARY KEY, distributor_name VARCHAR,
            retailer_name VARCHAR, outlet_type VARCHAR
        )""")
    for row in data["customers"]:
        conn.execute(f"INSERT INTO {schema}.dim_customer VALUES (?,?,?,?)", list(row))

    # dim_channel
    conn.execute(f"""
        CREATE TABLE {schema}.dim_channel (
            channel_key INTEGER PRIMARY KEY, channel_name VARCHAR
        )""")
    for row in CHANNELS:
        conn.execute(f"INSERT INTO {schema}.dim_channel VALUES (?,?)", list(row))

    # dim_sales_hierarchy
    conn.execute(f"""
        CREATE TABLE {schema}.dim_sales_hierarchy (
            hierarchy_key INTEGER PRIMARY KEY,
            so_code VARCHAR, so_name VARCHAR,
            asm_code VARCHAR, asm_name VARCHAR,
            zsm_code VARCHAR, zsm_name VARCHAR,
            nsm_code VARCHAR, nsm_name VARCHAR,
            zone_name VARCHAR, region_name VARCHAR
        )""")
    for row in data["hierarchy"]:
        conn.execute(f"INSERT INTO {schema}.dim_sales_hierarchy VALUES (?,?,?,?,?,?,?,?,?,?,?)", list(row))

    # dim_date
    conn.execute(f"""
        CREATE TABLE {schema}.dim_date (
            date_key INTEGER PRIMARY KEY, date DATE,
            year INTEGER, quarter INTEGER, month INTEGER,
            month_name VARCHAR, week INTEGER
        )""")
    d = START_DATE
    while d <= END_DATE:
        dk = date_key(d)
        conn.execute(f"INSERT INTO {schema}.dim_date VALUES (?,?,?,?,?,?,?)", [
            dk, d.isoformat(), d.year, (d.month-1)//3+1, d.month,
            d.strftime("%B"), d.isocalendar()[1]
        ])
        d += timedelta(days=1)

    # fact_secondary_sales
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

    products   = data["products"]           # list of tuples
    n_prod     = len(products)
    velocities = [p[7] for p in products]   # index 7 = velocity
    customers  = data["customers"]          # list of tuples
    n_cust     = len(customers)

    invoice_key = 1
    d = START_DATE
    while d <= END_DATE:
        # Base invoices/day ~8, scaled by seasonality + day-of-week noise
        base        = 8.0 * MONTH_MULT[d.month]
        dow_factor  = 0.6 if d.weekday() == 6 else (1.1 if d.weekday() in (3,4) else 1.0)
        n_invoices  = max(1, int(rng.gauss(base * dow_factor, base * 0.2)))

        for _ in range(n_invoices):
            # Pick product (velocity-weighted)
            p_idx   = weighted_choice(range(n_prod), velocities)
            prod    = products[p_idx]
            pk      = p_idx + 1
            val_min, val_max = prod[5], prod[6]
            base_margin_pct  = prod[8]

            # Add festive uplift to Chocolates/Snacks in Oct
            if d.month == 10 and prod[3] in ("Chocolate", "Snacks"):
                val_min = int(val_min * 1.4)
                val_max = int(val_max * 1.4)

            # Add summer uplift to Beverages/Coffee in Apr-Jun
            if d.month in (4, 5, 6) and prod[3] in ("Beverages", "Coffee"):
                val_min = int(val_min * 1.25)
                val_max = int(val_max * 1.25)

            geo_key = rng.randint(1, 15)
            hier_key = GEO_HIER[geo_key]

            cust_idx = rng.randint(0, n_cust-1)
            cust = customers[cust_idx]
            cust_key = cust[0]
            outlet_type = cust[3]
            chan_key = CHANNEL_BY_OUTLET.get(outlet_type, rng.randint(1,5))

            inv_val    = rng.randint(val_min, val_max)
            disc_pct   = round(rng.uniform(3, 14), 2)
            disc_amt   = round(inv_val * disc_pct / 100, 2)
            net_val    = round(inv_val - disc_amt, 2)
            quantity   = rng.randint(15, 250)
            margin_pct = round(rng.gauss(base_margin_pct, 2.5), 2)
            margin_pct = max(5.0, min(40.0, margin_pct))
            margin_amt = round(net_val * margin_pct / 100, 2)
            ret_flag   = rng.random() < 0.02   # 2 % return rate

            conn.execute(
                f"INSERT INTO {schema}.fact_secondary_sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [invoice_key, d.isoformat(), pk, geo_key, cust_key, chan_key,
                 date_key(d), hier_key,
                 f"INV{invoice_key:05d}-{client}",
                 inv_val, disc_amt, disc_pct, net_val,
                 quantity, margin_amt, margin_pct, ret_flag]
            )
            invoice_key += 1

        d += timedelta(days=1)

    fact_count = conn.execute(f"SELECT COUNT(*) FROM {schema}.fact_secondary_sales").fetchone()[0]
    print(f"    ✓ {fact_count:,} fact rows  |  date range {START_DATE} → {END_DATE}")


def main():
    print(f"Opening {DB_PATH}")
    conn = duckdb.connect(str(DB_PATH))

    for i, (tenant, data) in enumerate(TENANT_DATA.items()):
        schema = f"client_{tenant}"
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        seed_tenant(conn, schema, data, seed_offset=i * 100)

    conn.close()
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n✓ Done — DB size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
