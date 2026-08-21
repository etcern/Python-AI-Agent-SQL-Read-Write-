"""Database population utility for QueryMaster.

Generates sample ecommerce data or imports from external sources.
The SQL agent queries this database, so the more realistic the data,
the better the agent performs.

Usage:
    python scripts/populate_db.py --sample             Generate 100 customers, 200 products, 500 orders
    python scripts/populate_db.py --sample --big        Generate 500 customers, 1000 products, 5000 orders
    python scripts/populate_db.py --csv products.csv    Import a CSV file into a table
    python scripts/populate_db.py --huggingface         Import from HuggingFace (needs 'pip install datasets')
    python scripts/populate_db.py --reset               Drop all tables and recreate empty schema

Ref: https://docs.python.org/3/library/sqlite3.html
Ref: https://huggingface.co/docs/datasets/
"""

import argparse
import csv
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

# -- Resolve paths relative to project root --
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DB_DIR, "ecommerce.db")


# --- Schema ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    phone      TEXT,
    address    TEXT,
    city       TEXT,
    country    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    price       REAL NOT NULL,
    category    TEXT,
    in_stock    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    order_date   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    total_amount REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL
);
"""


# --- Sample data pools ---

FIRST_NAMES = [
    "Emma", "Liam", "Sophia", "Noah", "Olivia", "James", "Ava", "Lucas",
    "Mia", "Ethan", "Isabella", "Mason", "Charlotte", "Logan", "Amelia",
    "Alexander", "Harper", "Sebastian", "Ella", "Benjamin", "Luna", "Daniel",
    "Aria", "Henry", "Chloe", "Jack", "Penelope", "Owen", "Layla", "Samuel",
    "Nora", "Ryan", "Zoey", "Nathan", "Lily", "Caleb", "Eleanor", "Isaac",
    "Hannah", "Leo", "Stella", "Julian", "Aurora", "Gabriel", "Violet",
    "Max", "Scarlett", "Adrian", "Grace", "Dylan",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas",
    "Jackson", "White", "Harris", "Martin", "Thompson", "Robinson", "Clark",
    "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright",
    "Scott", "Torres", "Hill", "Green", "Adams", "Baker", "Nelson",
    "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris",
    "Reed", "Morgan",
]

CITIES = [
    ("New York", "US"), ("Los Angeles", "US"), ("London", "UK"),
    ("Berlin", "DE"), ("Paris", "FR"), ("Tokyo", "JP"),
    ("Sydney", "AU"), ("Toronto", "CA"), ("Amsterdam", "NL"),
    ("Barcelona", "ES"), ("Milan", "IT"), ("Seoul", "KR"),
    ("Munich", "DE"), ("Vienna", "AT"), ("Zurich", "CH"),
    ("Stockholm", "SE"), ("Oslo", "NO"), ("Dublin", "IE"),
    ("Singapore", "SG"), ("Dubai", "AE"),
]

CATEGORIES = {
    "Electronics": [
        ("Wireless Headphones", "Bluetooth over-ear headphones with noise cancellation", 79.99, 149.99),
        ("USB-C Hub", "7-in-1 USB-C adapter with HDMI, USB 3.0, and SD card reader", 29.99, 59.99),
        ("Mechanical Keyboard", "RGB mechanical keyboard with Cherry MX switches", 89.99, 179.99),
        ("Webcam HD", "1080p webcam with autofocus and built-in microphone", 39.99, 89.99),
        ("Portable SSD", "1TB portable SSD with USB 3.2 Gen 2", 69.99, 129.99),
        ("Smart Watch", "Fitness tracker with heart rate and GPS", 99.99, 299.99),
        ("Wireless Mouse", "Ergonomic wireless mouse with adjustable DPI", 19.99, 49.99),
        ("Monitor Stand", "Adjustable monitor arm with cable management", 34.99, 79.99),
        ("Power Bank", "20000mAh portable charger with fast charging", 24.99, 49.99),
        ("Tablet Stand", "Foldable aluminum tablet and phone stand", 14.99, 29.99),
    ],
    "Clothing": [
        ("Cotton T-Shirt", "100% organic cotton crew neck t-shirt", 12.99, 34.99),
        ("Denim Jeans", "Classic fit denim jeans with stretch comfort", 39.99, 89.99),
        ("Hoodie", "Pullover hoodie with kangaroo pocket", 29.99, 59.99),
        ("Running Shoes", "Lightweight running shoes with cushioned sole", 49.99, 129.99),
        ("Winter Jacket", "Waterproof insulated winter parka", 79.99, 199.99),
        ("Wool Scarf", "Merino wool scarf, unisex", 19.99, 39.99),
        ("Baseball Cap", "Adjustable cotton baseball cap", 9.99, 24.99),
        ("Leather Belt", "Genuine leather belt with metal buckle", 14.99, 39.99),
    ],
    "Books": [
        ("Python Crash Course", "Hands-on introduction to Python programming", 19.99, 39.99),
        ("Clean Code", "A handbook of agile software craftsmanship", 24.99, 44.99),
        ("Design Patterns", "Elements of reusable object-oriented software", 29.99, 54.99),
        ("The Pragmatic Programmer", "Your journey to mastery", 29.99, 49.99),
        ("SQL Cookbook", "Query solutions and techniques for database developers", 24.99, 44.99),
        ("AI & Machine Learning", "Introduction to artificial intelligence concepts", 34.99, 59.99),
    ],
    "Home & Garden": [
        ("LED Desk Lamp", "Dimmable LED desk lamp with USB charging port", 24.99, 49.99),
        ("Coffee Maker", "12-cup programmable drip coffee maker", 34.99, 79.99),
        ("Plant Pot Set", "Set of 3 ceramic plant pots with drainage", 14.99, 29.99),
        ("Blanket Throw", "Soft fleece throw blanket, 150x200cm", 19.99, 39.99),
        ("Kitchen Scale", "Digital kitchen scale with tare function", 12.99, 24.99),
        ("Water Bottle", "Insulated stainless steel water bottle, 750ml", 14.99, 29.99),
    ],
    "Sports": [
        ("Yoga Mat", "Non-slip yoga mat with carry strap, 6mm", 19.99, 39.99),
        ("Resistance Bands", "Set of 5 exercise resistance bands", 12.99, 24.99),
        ("Jump Rope", "Adjustable speed jump rope with ball bearings", 9.99, 19.99),
        ("Dumbbell Set", "Adjustable dumbbell set, 2x 10kg", 49.99, 99.99),
        ("Sports Bag", "Large gym bag with shoe compartment", 24.99, 49.99),
        ("Cycling Gloves", "Padded cycling gloves with grip", 14.99, 29.99),
    ],
}

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]


# --- Generators ---

def generate_customers(n: int) -> list[dict]:
    """Generate n random customer records."""
    customers = []
    used_emails = set()
    for _ in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@example.com"
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{random.randint(1, 9999)}@example.com"
        used_emails.add(email)
        city, country = random.choice(CITIES)
        created = datetime.now() - timedelta(days=random.randint(30, 730))
        customers.append({
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": f"+{random.randint(1, 99)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "address": f"{random.randint(1, 9999)} {random.choice(LAST_NAMES)} St",
            "city": city,
            "country": country,
            "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return customers


def generate_products() -> list[dict]:
    """Generate products from the category pools."""
    products = []
    for category, items in CATEGORIES.items():
        for name, desc, low_price, high_price in items:
            products.append({
                "name": name,
                "description": desc,
                "price": round(random.uniform(low_price, high_price), 2),
                "category": category,
                "in_stock": random.choices([1, 0], weights=[85, 15])[0],
            })
    return products


def generate_orders(n: int, customer_ids: list[int],
                    product_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Generate n orders with 1-5 items each. Returns (orders, order_items)."""
    orders = []
    items = []
    for _ in range(n):
        cid = random.choice(customer_ids)
        date = datetime.now() - timedelta(days=random.randint(1, 365))
        status = random.choices(
            ORDER_STATUSES,
            weights=[10, 15, 25, 45, 5],
        )[0]
        order = {
            "customer_id": cid,
            "order_date": date.strftime("%Y-%m-%d"),
            "status": status,
            "total_amount": 0.0,
        }
        # -- 1 to 5 items per order --
        num_items = random.randint(1, 5)
        chosen = random.sample(product_rows, min(num_items, len(product_rows)))
        total = 0.0
        for prod in chosen:
            qty = random.randint(1, 3)
            price = prod["price"]
            total += qty * price
            items.append({
                "order_id_placeholder": len(orders),
                "product_id": prod["id"],
                "quantity": qty,
                "unit_price": price,
            })
        order["total_amount"] = round(total, 2)
        orders.append(order)
    return orders, items


# --- Database operations ---

def connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def reset_db(conn: sqlite3.Connection):
    """Drop all tables and recreate the schema."""
    for table in ["order_items", "orders", "products", "customers", "sqlite_sequence"]:
        conn.execute(f"DROP TABLE IF EXISTS [{table}];")
    conn.commit()
    create_schema(conn)
    print("Database reset - empty schema created.")


def populate_sample(conn: sqlite3.Connection, big: bool = False):
    """Generate and insert sample data."""
    n_customers = 500 if big else 100
    n_orders = 5000 if big else 500

    create_schema(conn)

    # -- Check if data already exists --
    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if existing > 0:
        print(f"Database already has {existing} customers. Use --reset first to start fresh.")
        return

    # -- Customers --
    customers = generate_customers(n_customers)
    conn.executemany(
        "INSERT INTO customers (first_name, last_name, email, phone, address, city, country, created_at) "
        "VALUES (:first_name, :last_name, :email, :phone, :address, :city, :country, :created_at)",
        customers,
    )
    conn.commit()
    customer_ids = [r[0] for r in conn.execute("SELECT id FROM customers").fetchall()]
    print(f"  Inserted {len(customers)} customers")

    # -- Products --
    products = generate_products()
    conn.executemany(
        "INSERT INTO products (name, description, price, category, in_stock) "
        "VALUES (:name, :description, :price, :category, :in_stock)",
        products,
    )
    conn.commit()
    product_rows = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    print(f"  Inserted {len(products)} products")

    # -- Orders + items --
    orders, items = generate_orders(n_orders, customer_ids, product_rows)
    order_ids = []
    for order in orders:
        cur = conn.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount) "
            "VALUES (:customer_id, :order_date, :status, :total_amount)",
            order,
        )
        order_ids.append(cur.lastrowid)
    conn.commit()
    print(f"  Inserted {len(orders)} orders")

    for item in items:
        item["order_id"] = order_ids[item.pop("order_id_placeholder")]
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
        "VALUES (:order_id, :product_id, :quantity, :unit_price)",
        items,
    )
    conn.commit()
    print(f"  Inserted {len(items)} order items")
    print(f"Done! Database at: {DB_PATH}")


def import_csv(conn: sqlite3.Connection, csv_path: str):
    """Import a CSV file into a table (table name = filename without extension)."""
    table_name = os.path.splitext(os.path.basename(csv_path))[0]
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        print(f"CSV file is empty: {csv_path}")
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in columns)
    col_names = ", ".join(f"[{c}]" for c in columns)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS [{table_name}] (
            {', '.join(f'[{c}] TEXT' for c in columns)}
        )
    """)
    conn.executemany(
        f"INSERT INTO [{table_name}] ({col_names}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()
    print(f"Imported {len(rows)} rows into table '{table_name}' from {csv_path}")


def import_huggingface(conn: sqlite3.Connection):
    """Import an ecommerce dataset from HuggingFace.

    Requires: pip install datasets
    Ref: https://huggingface.co/docs/datasets/
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("=" * 60)
        print("HuggingFace 'datasets' library not installed.")
        print()
        print("To install it:")
        print("  pip install datasets")
        print()
        print("Then run this command again:")
        print("  python scripts/populate_db.py --huggingface")
        print("=" * 60)
        return

    print("Loading dataset from HuggingFace...")
    print("Using: 'rajistics/ecommerce_customer_data'")
    print()

    try:
        ds = load_dataset("rajistics/ecommerce_customer_data", split="train")
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        print()
        print("You can try other datasets:")
        print("  - 'maharshipandya/spotify-tracks-dataset'")
        print("  - 'alfredodeza/wine-ratings'")
        print("  - Search: https://huggingface.co/datasets?task_categories=tabular-classification")
        return

    # -- Convert to table --
    table_name = "hf_ecommerce"
    columns = ds.column_names
    col_defs = ", ".join(f"[{c}] TEXT" for c in columns)
    conn.execute(f"DROP TABLE IF EXISTS [{table_name}];")
    conn.execute(f"CREATE TABLE [{table_name}] ({col_defs});")

    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(f"[{c}]" for c in columns)
    batch = []
    for row in ds:
        batch.append(tuple(str(row.get(c, "")) for c in columns))
        if len(batch) >= 500:
            conn.executemany(
                f"INSERT INTO [{table_name}] ({col_names}) VALUES ({placeholders})",
                batch,
            )
            batch = []
    if batch:
        conn.executemany(
            f"INSERT INTO [{table_name}] ({col_names}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
    print(f"Imported {count} rows into table '{table_name}'")
    print(f"Your SQL agent can now query it: SELECT * FROM {table_name} LIMIT 10;")


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Populate the QueryMaster ecommerce database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/populate_db.py --sample            Small dataset (100 customers, ~40 products, 500 orders)
  python scripts/populate_db.py --sample --big      Large dataset (500 customers, ~40 products, 5000 orders)
  python scripts/populate_db.py --reset --sample    Wipe and regenerate
  python scripts/populate_db.py --csv mydata.csv    Import CSV as a new table
  python scripts/populate_db.py --huggingface       Import from HuggingFace (needs 'pip install datasets')
        """,
    )
    parser.add_argument("--sample", action="store_true", help="Generate sample ecommerce data")
    parser.add_argument("--big", action="store_true", help="Generate larger dataset (with --sample)")
    parser.add_argument("--csv", type=str, help="Path to a CSV file to import")
    parser.add_argument("--huggingface", action="store_true", help="Import from HuggingFace dataset")
    parser.add_argument("--reset", action="store_true", help="Drop all tables first")

    args = parser.parse_args()

    if not any([args.sample, args.csv, args.huggingface, args.reset]):
        parser.print_help()
        return

    conn = connect()

    if args.reset:
        reset_db(conn)

    if args.sample:
        populate_sample(conn, big=args.big)

    if args.csv:
        import_csv(conn, args.csv)

    if args.huggingface:
        import_huggingface(conn)

    conn.close()


if __name__ == "__main__":
    main()
