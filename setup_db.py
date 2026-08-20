"""Generate the SQLite e-commerce database with sample data."""

import sqlite3
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ecommerce.db")

CATEGORIES = [
    "Electronics", "Clothing", "Home & Kitchen", "Books",
    "Sports & Outdoors", "Beauty", "Toys & Games", "Automotive",
]

PRODUCT_TEMPLATES = {
    "Electronics": [
        ("Wireless Bluetooth Headphones", 49.99, "Premium over-ear headphones with noise cancellation and 30-hour battery life"),
        ("USB-C Fast Charging Cable 6ft", 12.99, "Braided nylon cable with 100W power delivery support"),
        ("Portable Power Bank 20000mAh", 34.99, "Slim portable charger with dual USB-A and USB-C ports"),
        ("Mechanical Gaming Keyboard", 79.99, "RGB backlit keyboard with Cherry MX Blue switches"),
        ("Wireless Gaming Mouse", 44.99, "Ergonomic mouse with 16000 DPI sensor and 6 programmable buttons"),
        ("4K Webcam with Microphone", 59.99, "Ultra HD webcam with auto-focus and built-in noise-canceling mic"),
        ("Smart LED Light Strip 10m", 24.99, "WiFi-enabled RGB light strip with app control and music sync"),
        ("Portable Bluetooth Speaker", 39.99, "Waterproof speaker with 360-degree sound and 12-hour playtime"),
        ("64GB USB 3.0 Flash Drive", 9.99, "High-speed flash drive with retractable connector"),
        ("Wireless Charging Pad", 19.99, "Qi-compatible fast wireless charger for phones and earbuds"),
        ("Noise Cancelling Earbuds", 69.99, "True wireless earbuds with ANC and transparency mode"),
        ("HDMI 2.1 Cable 3m", 14.99, "8K-ready HDMI cable with eARC support"),
    ],
    "Clothing": [
        ("Men's Classic Fit T-Shirt", 18.99, "Soft cotton crew neck t-shirt available in multiple colors"),
        ("Women's Running Shorts", 24.99, "Lightweight moisture-wicking shorts with hidden pocket"),
        ("Unisex Zip-Up Hoodie", 39.99, "Fleece-lined hoodie with front kangaroo pocket"),
        ("Men's Slim Fit Jeans", 44.99, "Stretch denim jeans with classic five-pocket design"),
        ("Women's Yoga Leggings", 29.99, "High-waist leggings with four-way stretch fabric"),
        ("Wool Blend Beanie Hat", 14.99, "Warm knitted beanie with fold-up cuff design"),
        ("Athletic Crew Socks 6-Pack", 16.99, "Cushioned socks with arch support and moisture management"),
        ("Waterproof Rain Jacket", 59.99, "Packable rain jacket with sealed seams and adjustable hood"),
        ("Casual Canvas Sneakers", 34.99, "Classic low-top sneakers with rubber sole"),
        ("Leather Belt", 22.99, "Genuine leather belt with brushed nickel buckle"),
        ("Flannel Plaid Shirt", 32.99, "Button-down flannel shirt in classic plaid pattern"),
        ("Insulated Winter Gloves", 19.99, "Touchscreen-compatible gloves with thermal lining"),
    ],
    "Home & Kitchen": [
        ("Stainless Steel Water Bottle 750ml", 16.99, "Double-wall insulated bottle keeps drinks cold 24hr or hot 12hr"),
        ("Non-Stick Frying Pan 28cm", 27.99, "PFOA-free ceramic coated pan with ergonomic handle"),
        ("Bamboo Cutting Board Set", 22.99, "Set of 3 boards in different sizes with juice groove"),
        ("Electric Kettle 1.7L", 32.99, "Rapid boil kettle with temperature control and auto shut-off"),
        ("Silicone Kitchen Utensil Set", 19.99, "Heat-resistant 8-piece set with wooden handles"),
        ("French Press Coffee Maker", 24.99, "Borosilicate glass press with stainless steel filter"),
        ("LED Desk Lamp with USB Port", 29.99, "Adjustable brightness lamp with wireless charging base"),
        ("Memory Foam Pillow", 34.99, "Contoured cervical pillow with cooling gel layer"),
        ("Glass Food Storage Set 10pc", 28.99, "Oven-safe glass containers with snap-lock lids"),
        ("Stainless Steel Knife Set 6pc", 45.99, "Forged knives with ergonomic handles and wooden block"),
        ("Cast Iron Skillet 12 inch", 38.99, "Pre-seasoned cast iron with helper handle"),
        ("Automatic Soap Dispenser", 21.99, "Touchless dispenser with adjustable volume control"),
        ("Cotton Bath Towel Set 4pc", 32.99, "Quick-dry towels in assorted colors"),
    ],
    "Books": [
        ("Python Programming Masterclass", 39.99, "Comprehensive guide covering Python from basics to advanced topics"),
        ("The Art of SQL Queries", 29.99, "Learn to write efficient SQL queries with real-world examples"),
        ("Machine Learning Fundamentals", 44.99, "Introduction to ML algorithms with hands-on projects"),
        ("Data Structures & Algorithms", 34.99, "Essential computer science concepts with code examples"),
        ("Web Development Bootcamp Guide", 32.99, "Full-stack web development from HTML to deployment"),
        ("Cloud Computing Essentials", 37.99, "Guide to AWS, Azure, and GCP fundamentals"),
        ("Cybersecurity for Beginners", 27.99, "Practical guide to network security and ethical hacking"),
        ("DevOps Handbook", 41.99, "Best practices for CI/CD, containers, and infrastructure"),
        ("AI Ethics and Society", 24.99, "Exploring the social impact of artificial intelligence"),
        ("Linux Command Line Mastery", 22.99, "From shell basics to advanced scripting techniques"),
        ("Database Design Principles", 33.99, "Relational database design and normalization guide"),
        ("Agile Project Management", 28.99, "Scrum and Kanban methodologies for software teams"),
    ],
    "Sports & Outdoors": [
        ("Yoga Mat 6mm Thick", 24.99, "Non-slip TPE mat with alignment lines and carrying strap"),
        ("Resistance Bands Set 5pc", 14.99, "Latex-free bands with 5 resistance levels"),
        ("Adjustable Dumbbell Set 20kg", 89.99, "Quick-change weight system from 2kg to 20kg per hand"),
        ("Camping Headlamp 1000 Lumens", 19.99, "Rechargeable headlamp with red light mode"),
        ("Insulated Hiking Backpack 30L", 54.99, "Ventilated back panel with hydration bladder compartment"),
        ("Jump Rope Speed Cable", 11.99, "Adjustable length with ball-bearing handles"),
        ("Foam Roller 45cm", 17.99, "High-density EVA foam for deep tissue massage"),
        ("Cycling Water Bottle 600ml", 8.99, "BPA-free squeeze bottle with dust cap"),
        ("Tennis Balls 4-Pack", 7.99, "ITF-approved pressurized balls for all court types"),
        ("Fitness Tracker Watch", 49.99, "Heart rate monitor with sleep tracking and GPS"),
        ("Swim Goggles Anti-Fog", 15.99, "UV protection lenses with adjustable silicone strap"),
        ("Compression Knee Sleeve", 18.99, "Neoprene sleeve for joint support during activity"),
    ],
    "Beauty": [
        ("Vitamin C Face Serum 30ml", 19.99, "Brightening serum with hyaluronic acid and vitamin E"),
        ("Natural Bamboo Toothbrush 4pk", 8.99, "Biodegradable brushes with charcoal-infused bristles"),
        ("Moisturizing Body Lotion 500ml", 14.99, "Shea butter formula for all-day hydration"),
        ("Hair Repair Argan Oil 100ml", 16.99, "Cold-pressed organic argan oil for hair and skin"),
        ("SPF 50 Mineral Sunscreen", 22.99, "Reef-safe zinc oxide sunscreen with no white cast"),
        ("Exfoliating Face Scrub 150ml", 12.99, "Gentle walnut shell scrub with aloe vera"),
        ("Retinol Night Cream 50ml", 28.99, "Anti-aging cream with peptides and niacinamide"),
        ("Makeup Brush Set 12pc", 24.99, "Synthetic bristle brushes with vegan leather case"),
        ("Lip Balm Variety Pack 5pc", 9.99, "Organic beeswax balms in assorted flavors"),
        ("Charcoal Face Mask 5-Pack", 11.99, "Pore-cleansing sheet masks with activated charcoal"),
        ("Nail Polish Set 6 Colors", 17.99, "Long-lasting formula with quick-dry top coat"),
        ("Electric Facial Cleansing Brush", 34.99, "Waterproof brush with 3 speed settings"),
    ],
    "Toys & Games": [
        ("1000-Piece Jigsaw Puzzle", 14.99, "Scenic landscape puzzle with poster guide"),
        ("Building Blocks Set 500pc", 29.99, "Compatible with major brands, includes storage box"),
        ("Remote Control Car 1:16", 34.99, "4WD off-road RC car with rechargeable battery"),
        ("Board Game Strategy Collection", 24.99, "Classic strategy game for 2-6 players ages 10+"),
        ("Magnetic Drawing Board", 12.99, "Erasable drawing pad with stamps and stylus"),
        ("Science Experiment Kit", 27.99, "50+ experiments covering chemistry and physics"),
        ("Wooden Train Set 40pc", 32.99, "Compatible track set with bridges and accessories"),
        ("Card Game Party Pack", 16.99, "Fast-paced card game for groups of 3-8 players"),
        ("Plush Stuffed Animal 30cm", 15.99, "Ultra-soft polyester fill with embroidered features"),
        ("Outdoor Kite Delta Wing", 11.99, "Easy-fly kite with 50m line and winder"),
        ("Rubik's Speed Cube 3x3", 9.99, "Smooth rotation cube with adjustable tension"),
        ("Craft Kit for Kids", 19.99, "Art supplies set with beads, yarn, and instructions"),
    ],
    "Automotive": [
        ("Dash Cam 1080p", 44.99, "Wide-angle camera with night vision and loop recording"),
        ("Car Phone Mount Magnetic", 13.99, "Universal air vent mount with strong magnets"),
        ("Tire Pressure Gauge Digital", 11.99, "Backlit display with 4 measurement units"),
        ("Car Vacuum Cleaner 12V", 29.99, "Portable vacuum with HEPA filter and attachments"),
        ("LED Interior Light Kit", 18.99, "App-controlled RGB lights with music sync"),
        ("Emergency Roadside Kit", 39.99, "Jumper cables, flashlight, first aid, and more"),
        ("Windshield Sun Shade", 14.99, "Foldable reflective shade for UV protection"),
        ("Leather Steering Wheel Cover", 16.99, "Anti-slip cover with breathable perforations"),
        ("Car Air Freshener 3-Pack", 9.99, "Long-lasting vent clip fresheners in assorted scents"),
        ("Trunk Organizer Collapsible", 22.99, "Multi-compartment organizer with reinforced base"),
        ("Microfiber Cleaning Cloth 10pk", 8.99, "Scratch-free cloths for interior and exterior"),
        ("Portable Jump Starter 12V", 59.99, "12000mAh power bank with jumper cables and USB ports"),
    ],
}

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Andrew", "Emily", "Paul", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Bond", "Reed", "Cook", "Morgan", "Bell", "Murphy",
    "Bailey", "Cooper", "Richardson", "Cox", "Howard", "Ward", "Peterson", "Gray",
]

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]


def create_tables(cursor: sqlite3.Cursor):
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            in_stock INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            city TEXT,
            country TEXT NOT NULL DEFAULT 'US',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            total_amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    """)


def seed_products(cursor: sqlite3.Cursor):
    products = []
    for category, items in PRODUCT_TEMPLATES.items():
        for name, price, description in items:
            in_stock = 1 if random.random() > 0.1 else 0
            products.append((name, description, price, category, in_stock))

    cursor.executemany(
        "INSERT INTO products (name, description, price, category, in_stock) VALUES (?, ?, ?, ?, ?)",
        products,
    )
    return len(products)


def seed_customers(cursor: sqlite3.Cursor, count: int = 100):
    random.shuffle(FIRST_NAMES)
    random.shuffle(LAST_NAMES)
    customers = []
    emails_seen = set()

    cities = [
        ("New York", "US"), ("Los Angeles", "US"), ("Chicago", "US"),
        ("Houston", "US"), ("Phoenix", "US"), ("San Antonio", "US"),
        ("San Diego", "US"), ("Dallas", "US"), ("Austin", "US"),
        ("Seattle", "US"), ("Denver", "US"), ("Boston", "US"),
        ("Portland", "US"), ("Nashville", "US"), ("Atlanta", "US"),
        ("Miami", "US"), ("Toronto", "CA"), ("Vancouver", "CA"),
        ("London", "UK"), ("Berlin", "DE"),
    ]

    for i in range(count):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        if email in emails_seen:
            email = f"{first.lower()}.{last.lower()}{i}{random.randint(100,999)}@example.com"
        emails_seen.add(email)

        phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        city, country = random.choice(cities)
        address = f"{random.randint(1, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Maple', 'Cedar', 'Elm', 'Park', 'Lake', 'Hill', 'River'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Ln', 'Way'])}"
        created_at = (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 730))).isoformat()

        customers.append((first, last, email, phone, address, city, country, created_at))

    cursor.executemany(
        "INSERT INTO customers (first_name, last_name, email, phone, address, city, country, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        customers,
    )
    return count


def seed_orders(cursor: sqlite3.Cursor, num_customers: int, num_orders: int = 500):
    cursor.execute("SELECT id, price FROM products")
    products = cursor.fetchall()

    for _ in range(num_orders):
        customer_id = random.randint(1, num_customers)
        order_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 500))).isoformat()
        status = random.choices(
            ORDER_STATUSES, weights=[10, 15, 20, 50, 5], k=1
        )[0]

        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES (?, ?, ?, 0)",
            (customer_id, order_date, status),
        )
        order_id = cursor.lastrowid

        num_items = random.randint(1, 5)
        chosen = random.sample(products, min(num_items, len(products)))
        total = 0.0

        for prod_id, prod_price in chosen:
            qty = random.randint(1, 3)
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, prod_id, qty, prod_price),
            )
            total += prod_price * qty

        cursor.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (round(total, 2), order_id),
        )

    return num_orders


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Creating tables...")
    create_tables(cursor)

    print("Seeding products...")
    num_products = seed_products(cursor)
    print(f"  -> {num_products} products inserted")

    print("Seeding customers...")
    num_customers = seed_customers(cursor, count=100)
    print(f"  -> {num_customers} customers inserted")

    print("Seeding orders and order items...")
    num_orders = seed_orders(cursor, num_customers, num_orders=500)
    print(f"  -> {num_orders} orders inserted")

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM order_items")
    num_items = cursor.fetchone()[0]
    print(f"  -> {num_items} order items inserted")

    size_bytes = os.path.getsize(DB_PATH)
    print(f"\nDatabase created at: {DB_PATH}")
    print(f"Database size: {size_bytes / 1024:.1f} KB")

    conn.close()


if __name__ == "__main__":
    main()
