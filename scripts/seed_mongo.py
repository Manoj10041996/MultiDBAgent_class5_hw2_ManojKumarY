"""
seed_mongo.py — Seeds the StockPulse MongoDB database.

Collections: reviews, support_tickets, activity_logs

Usage:
    python -m scripts.seed_mongo
    # or
    uv run python scripts/seed_mongo.py
"""

import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.environ["MONGO_URL"]
MONGO_DB  = os.environ.get("MONGO_DB", "stockpulse")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

REVIEWS = [
    # Wireless Mouse reviews
    {"product_id": "MOUSE-001", "customer_id": "C001", "rating": 5,
     "comment": "Excellent mouse, very responsive and comfortable for all-day use.",
     "date": days_ago(2)},
    {"product_id": "MOUSE-001", "customer_id": "C002", "rating": 4,
     "comment": "Good value for money. Scroll wheel feels a little stiff.",
     "date": days_ago(5)},
    {"product_id": "MOUSE-001", "customer_id": "C003", "rating": 1,
     "comment": "Stopped working after two weeks. Very disappointed.",
     "date": days_ago(3)},
    {"product_id": "MOUSE-001", "customer_id": "C004", "rating": 1,
     "comment": "Wireless connection keeps dropping. Would not recommend.",
     "date": days_ago(1)},
    {"product_id": "MOUSE-001", "customer_id": "C005", "rating": 2,
     "comment": "Poor build quality. The left click button feels loose.",
     "date": days_ago(7)},
    # Keyboard reviews
    {"product_id": "KEYBRD-001", "customer_id": "C006", "rating": 5,
     "comment": "Best keyboard I have ever owned. Tactile feedback is perfect.",
     "date": days_ago(4)},
    {"product_id": "KEYBRD-001", "customer_id": "C007", "rating": 4,
     "comment": "Great typing experience, a bit loud for open offices.",
     "date": days_ago(6)},
    {"product_id": "KEYBRD-001", "customer_id": "C008", "rating": 1,
     "comment": "Three keys stopped registering within a month of purchase.",
     "date": days_ago(8)},
    # Headphone reviews
    {"product_id": "HEAD-001", "customer_id": "C009", "rating": 5,
     "comment": "Incredible noise cancellation. Totally worth the price.",
     "date": days_ago(3)},
    {"product_id": "HEAD-001", "customer_id": "C010", "rating": 3,
     "comment": "Sound quality is good but they get uncomfortable after 2 hours.",
     "date": days_ago(9)},
    # USB Hub reviews
    {"product_id": "USBHUB-001", "customer_id": "C001", "rating": 5,
     "comment": "Works perfectly with my MacBook Pro. All 7 ports are functional.",
     "date": days_ago(1)},
    {"product_id": "USBHUB-001", "customer_id": "C003", "rating": 2,
     "comment": "Two ports stopped working after a month. Unreliable.",
     "date": days_ago(12)},
    # SSD reviews
    {"product_id": "SSD-001", "customer_id": "C006", "rating": 5,
     "comment": "Lightning fast transfer speeds. Compact and durable.",
     "date": days_ago(5)},
    {"product_id": "SSD-001", "customer_id": "C008", "rating": 4,
     "comment": "Great performance, wish the cable was longer.",
     "date": days_ago(3)},
]

# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------

SUPPORT_TICKETS = [
    {"ticket_id": "TKT-001", "customer_id": "C003", "product_id": "MOUSE-001",
     "issue": "Wireless connection keeps dropping after 2 metres",
     "status": "open", "created_at": days_ago(1)},
    {"ticket_id": "TKT-002", "customer_id": "C007", "product_id": "KEYBRD-001",
     "issue": "Package arrived with damaged box, keyboard keys are scratched",
     "status": "in_progress", "created_at": days_ago(2)},
    {"ticket_id": "TKT-003", "customer_id": "C004", "product_id": "MOUSE-001",
     "issue": "Wrong item delivered — received a wired mouse instead of wireless",
     "status": "open", "created_at": days_ago(3)},
    {"ticket_id": "TKT-004", "customer_id": "C009", "product_id": "HEAD-001",
     "issue": "Shipment delayed by 5 days, no tracking update since last week",
     "status": "open", "created_at": days_ago(4)},
    {"ticket_id": "TKT-005", "customer_id": "C008", "product_id": "KEYBRD-001",
     "issue": "Keys K, L, and Enter no longer register keypresses",
     "status": "open", "created_at": days_ago(5)},
    {"ticket_id": "TKT-006", "customer_id": "C002", "product_id": "USBHUB-001",
     "issue": "USB hub ports 4 and 5 are non-functional after firmware update",
     "status": "resolved", "created_at": days_ago(10)},
    {"ticket_id": "TKT-007", "customer_id": "C010", "product_id": "HEAD-001",
     "issue": "Requesting refund — product does not match website description",
     "status": "in_progress", "created_at": days_ago(6)},
    {"ticket_id": "TKT-008", "customer_id": "C005", "product_id": "MOUSE-001",
     "issue": "Left click button stuck — cannot single click, only double-clicks",
     "status": "open", "created_at": days_ago(1)},
    {"ticket_id": "TKT-009", "customer_id": "C001", "product_id": "SSD-001",
     "issue": "SSD not recognised on Windows 11 after formatted on Mac",
     "status": "resolved", "created_at": days_ago(15)},
    {"ticket_id": "TKT-010", "customer_id": "C006", "product_id": "KEYBRD-001",
     "issue": "Delayed shipment — order placed 10 days ago, still not shipped",
     "status": "open", "created_at": days_ago(2)},
]

# ---------------------------------------------------------------------------
# Activity Logs
# ---------------------------------------------------------------------------

ACTIONS = ["view", "add_to_cart", "purchase", "wishlist"]
PRODUCTS_LIST = ["MOUSE-001", "KEYBRD-001", "USBHUB-001", "HEAD-001", "SSD-001",
                 "LAMP-001", "CHAIR-001", "STAND-001"]
PAGES = ["/products", "/cart", "/checkout", "/product-detail"]

def generate_activity_logs(n: int = 60) -> list[dict]:
    logs = []
    random.seed(42)
    for i in range(n):
        logs.append({
            "user_id": f"U{random.randint(1, 20):03d}",
            "action": random.choice(ACTIONS),
            "product_id": random.choice(PRODUCTS_LIST),
            "page": random.choice(PAGES),
            "timestamp": days_ago(random.randint(0, 30)),
        })
    return logs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed():
    print("Connecting to MongoDB…")
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]

    # Drop and recreate collections
    for col in ["reviews", "support_tickets", "activity_logs"]:
        db.drop_collection(col)
        print(f"  Dropped & recreated '{col}'")

    print("Inserting reviews…")
    db.reviews.insert_many(REVIEWS)

    print("Inserting support tickets…")
    db.support_tickets.insert_many(SUPPORT_TICKETS)

    print("Inserting activity logs…")
    db.activity_logs.insert_many(generate_activity_logs(60))

    # Indexes for common query patterns
    db.reviews.create_index([("product_id", 1), ("rating", 1)])
    db.support_tickets.create_index([("status", 1), ("created_at", -1)])
    db.activity_logs.create_index([("user_id", 1), ("timestamp", -1)])

    client.close()
    print("✅  MongoDB seeded successfully.")


if __name__ == "__main__":
    seed()
