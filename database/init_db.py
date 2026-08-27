"""Create tables and seed demo data: waste categories (from config), a
demo city's locations/bins, and one user per role.

Run: python -m database.init_db
"""
from __future__ import annotations

import random

from database.db import engine, get_session
from database.models import Base, Bin, Location, User, WasteCategory
from utils.config import waste_categories
from utils.security import hash_password

# Demo locations around a fictional zone (coordinates centered near the
# depot in config/settings.yaml so the routing demo has a compact,
# realistic-looking map). In production these come from GPS-tagged bin
# installations, not this seed list.
DEMO_LOCATIONS = [
    ("City Hospital",        "hospital",    28.6304, 77.2177),
    ("Central Market",       "market",      28.6562, 77.2410),
    ("Green Valley School",  "school",      28.5921, 77.2290),
    ("Sunrise Residency",    "residential", 28.6100, 77.1855),
    ("Metro Plaza",          "commercial",  28.6270, 77.2080),
    ("Lakeview Park",        "park",        28.6005, 77.2410),
    ("Riverside Colony",     "residential", 28.6450, 77.1990),
    ("Tech Park One",        "commercial",  28.6180, 77.2530),
    ("Community Health Ctr", "hospital",    28.5985, 77.1970),
    ("Old Town Bazaar",      "market",      28.6390, 77.2260),
    ("Hillcrest School",     "school",      28.6055, 77.2530),
    ("Palm Residency",       "residential", 28.6520, 77.2150),
]

DEMO_USERS = [
    ("admin", "Admin123!", "System Administrator", "admin"),
    ("operator1", "Operator123!", "Ramesh Kumar (Operator)", "operator"),
    ("operator2", "Operator123!", "Sita Devi (Operator)", "operator"),
    ("citizen1", "Citizen123!", "Anjali Singh (Citizen)", "citizen"),
]


def seed(session):
    if session.query(WasteCategory).count() == 0:
        for key, cfg in waste_categories().items():
            session.add(
                WasteCategory(
                    key=key,
                    label=cfg["label"],
                    bin_stream=cfg["bin_stream"],
                    bin_color=cfg["bin_color"],
                    recyclable=cfg["recyclable"],
                    description=cfg.get("description"),
                )
            )
        session.flush()

    if session.query(Location).count() == 0:
        for name, ltype, lat, lon in DEMO_LOCATIONS:
            session.add(
                Location(name=name, address=f"{name}, Demo Zone", latitude=lat, longitude=lon, location_type=ltype)
            )
        session.flush()

    if session.query(Bin).count() == 0:
        categories = session.query(WasteCategory).all()
        locations = session.query(Location).all()
        rng = random.Random(42)
        bin_counter = 1
        for location in locations:
            # Each location hosts one bin per recyclable-relevant stream plus
            # organic + other, mirroring real multi-stream bin clusters.
            for cat in categories:
                if rng.random() < 0.55:  # not every location gets every stream
                    continue
                session.add(
                    Bin(
                        bin_code=f"BIN-{bin_counter:04d}",
                        location_id=location.id,
                        waste_category_id=cat.id,
                        capacity_liters=rng.choice([120.0, 240.0, 360.0]),
                        current_fill_level=rng.uniform(5, 35),
                        status="normal",
                    )
                )
                bin_counter += 1
        session.flush()

    if session.query(User).count() == 0:
        for username, password, full_name, role in DEMO_USERS:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    role=role,
                )
            )
        session.flush()


def main():
    Base.metadata.create_all(engine)
    with get_session() as session:
        seed(session)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
