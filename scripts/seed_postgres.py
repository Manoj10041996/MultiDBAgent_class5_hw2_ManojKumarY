"""
seed_postgres.py — Seeds the StockPulse Postgres database.

Creates tables: products, customers, orders
Then inserts realistic e-commerce data.

Usage:
    python -m scripts.seed_postgres
    # or
    uv run python scripts/seed_postgres.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.environ["POSTGRES_URL"]

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    email       TEXT        NOT NULL UNIQUE,
    city        TEXT        NOT NULL
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    stock_qty   INT         NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    customer_id INT         REFERENCES customers(id),
    product_id  INT         REFERENCES products(id),
    quantity    INT         NOT NULL,
    total       NUMERIC(10, 2) NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'completed',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

CUSTOMERS = [
    ("Alice Martin",    "alice@example.com",   "New York"),
    ("Bob Chen",        "bob@example.com",     "San Francisco"),
    ("Carol Williams",  "carol@example.com",   "Chicago"),
    ("David Lee",       "david@example.com",   "Austin"),
    ("Eva Patel",       "eva@example.com",     "Seattle"),
    ("Frank Garcia",    "frank@example.com",   "Boston"),
    ("Grace Kim",       "grace@example.com",   "Denver"),
    ("Henry Brown",     "henry@example.com",   "Miami"),
    ("Irene Johnson",   "irene@example.com",   "Atlanta"),
    ("Jack Wilson",     "jack@example.com",    "Portland"),
]

PRODUCTS = [
    ("Wireless Mouse",        "Electronics",    29.99,  142),
    ("Mechanical Keyboard",   "Electronics",    89.99,   38),
    ("USB-C Hub 7-Port",      "Electronics",    39.99,   75),
    ("4K Webcam",             "Electronics",    79.99,   21),
    ("Noise Cancelling Headphones", "Electronics", 149.99, 15),
    ("Ergonomic Office Chair","Furniture",     299.99,    8),
    ("Standing Desk",         "Furniture",     499.99,    4),
    ("Desk Lamp LED",         "Furniture",      34.99,   90),
    ("Laptop Stand Adjustable","Accessories",   49.99,   55),
    ("Cable Management Kit",  "Accessories",    14.99,  200),
    ("Screen Cleaning Kit",   "Accessories",     9.99,  350),
    ("Blue Light Glasses",    "Accessories",    24.99,   80),
    ("Wrist Rest Pad",        "Accessories",    19.99,  110),
    ("Monitor Privacy Screen","Accessories",    59.99,   30),
    ("Portable SSD 1TB",      "Storage",       109.99,   45),
]

# (customer_idx, product_idx, quantity, status, days_ago)
ORDERS = [
    (0, 0, 3, "completed",  2),   # Alice — Wireless Mouse x3
    (0, 8, 1, "completed",  5),   # Alice — Laptop Stand
    (1, 1, 1, "completed",  1),   # Bob — Keyboard
    (1, 2, 2, "completed",  3),   # Bob — USB Hub x2
    (2, 4, 1, "completed",  7),   # Carol — Headphones
    (2, 5, 1, "completed", 30),   # Carol — Chair
    (3, 0, 5, "completed",  4),   # David — Mouse x5
    (3, 3, 1, "completed",  6),   # David — Webcam
    (4, 6, 1, "pending",   15),   # Eva — Standing Desk (pending)
    (4, 9, 3, "completed",  2),   # Eva — Cable Kit x3
    (5, 0, 2, "completed",  1),   # Frank — Mouse x2
    (5, 7, 1, "completed",  9),   # Frank — Lamp
    (6, 14,1, "completed",  3),   # Grace — SSD
    (6, 10,2, "completed",  5),   # Grace — Cleaning Kit x2
    (7, 1, 1, "returned",  20),   # Henry — Keyboard (returned)
    (7, 11,1, "completed", 11),   # Henry — Blue Light Glasses
    (8, 0, 4, "completed",  2),   # Irene — Mouse x4
    (8, 12,2, "completed",  4),   # Irene — Wrist Rest x2
    (9, 13,1, "completed",  8),   # Jack — Privacy Screen
    (9, 8, 1, "completed",  6),   # Jack — Laptop Stand
    # Extra mouse orders to make it a top seller
    (1, 0, 2, "completed", 10),
    (2, 0, 1, "completed", 12),
    (3, 0, 3, "completed",  3),
    (4, 0, 1, "completed",  1),
    (5, 0, 2, "completed", 14),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed():
    print("Connecting to Postgres…")
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Running DDL…")
    cur.execute(DDL)

    print("Inserting customers…")
    customer_ids = []
    for name, email, city in CUSTOMERS:
        cur.execute(
            "INSERT INTO customers (name, email, city) VALUES (%s, %s, %s) RETURNING id",
            (name, email, city),
        )
        customer_ids.append(cur.fetchone()[0])

    print("Inserting products…")
    product_ids = []
    for name, category, price, stock in PRODUCTS:
        cur.execute(
            "INSERT INTO products (name, category, price, stock_qty) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, category, price, stock),
        )
        product_ids.append(cur.fetchone()[0])

    print("Inserting orders…")
    for cust_idx, prod_idx, qty, status, days_ago in ORDERS:
        cust_id = customer_ids[cust_idx]
        prod_id = product_ids[prod_idx]
        price = PRODUCTS[prod_idx][2]
        total = round(price * qty, 2)
        cur.execute(
            """
            INSERT INTO orders (customer_id, product_id, quantity, total, status, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW() - INTERVAL '%s days')
            """,
            (cust_id, prod_id, qty, total, status, days_ago),
        )

    cur.close()
    conn.close()
    print("✅  Postgres seeded successfully.")


if __name__ == "__main__":
    seed()
