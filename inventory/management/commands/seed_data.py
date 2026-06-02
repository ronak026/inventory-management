"""Populate the database with realistic sample data for demos & testing.

Usage:
    python manage.py seed_data            # default volumes
    python manage.py seed_data --flush    # wipe app data first

Creates demo users (admin / manager / staff), categories, suppliers,
products, stock transactions and purchase orders.
"""
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from inventory.models import StockTransaction, TransactionType
from products.models import Category, Product, ProductStatus, Unit
from purchases.models import PurchaseItem, PurchaseOrder, PurchaseStatus
from suppliers.models import Supplier

User = get_user_model()

CATEGORIES = [
    ("Electronics", "Phones, accessories and gadgets"),
    ("Stationery", "Office and school supplies"),
    ("Groceries", "Food and household consumables"),
    ("Hardware", "Tools and building supplies"),
    ("Apparel", "Clothing and accessories"),
]

PRODUCT_NAMES = {
    "Electronics": ["USB-C Cable", "Wireless Mouse", "Bluetooth Speaker", "Power Bank 10000mAh", "HDMI Adapter"],
    "Stationery": ["A4 Notebook", "Ballpoint Pen (Box)", "Stapler", "Sticky Notes", "Whiteboard Marker"],
    "Groceries": ["Basmati Rice 5kg", "Olive Oil 1L", "Instant Coffee 200g", "Green Tea 100 bags", "Sugar 1kg"],
    "Hardware": ["Claw Hammer", "Screwdriver Set", "Measuring Tape 5m", "LED Bulb 9W", "Extension Cord"],
    "Apparel": ["Cotton T-Shirt", "Denim Jeans", "Hooded Sweatshirt", "Sports Socks (Pack)", "Baseball Cap"],
}

SUPPLIERS = [
    ("Global Traders Ltd", "Anil Mehta", "anil@globaltraders.com", "+91 98200 11223", "27AAACG1234A1Z5"),
    ("Prime Distributors", "Sara Khan", "sara@primedist.com", "+91 99300 44556", "29AABCP6789B1Z2"),
    ("Metro Wholesale", "John Carter", "john@metrowholesale.com", "+1 415 555 0182", "US-VAT-99812"),
    ("Sunrise Imports", "Li Wei", "li@sunriseimports.com", "+86 138 0011 2233", "CN-VAT-55120"),
]


class Command(BaseCommand):
    help = "Seed the database with sample inventory data."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing app data first.")
        parser.add_argument("--transactions", type=int, default=120, help="Number of stock transactions to create.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data…")
            StockTransaction.objects.all().delete()
            PurchaseItem.objects.all().delete()
            PurchaseOrder.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Supplier.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        self._create_users()
        categories = self._create_categories()
        suppliers = self._create_suppliers()
        products = self._create_products(categories)
        self._create_transactions(products, options["transactions"])
        self._create_purchases(suppliers, products)
        self._create_production(products)

        self.stdout.write(self.style.SUCCESS("\nSample data created successfully!"))
        self.stdout.write("Login credentials (password = 'password123' for all):")
        self.stdout.write("  admin / password123      (Admin)")
        self.stdout.write("  manager / password123    (Inventory Manager)")
        self.stdout.write("  staff / password123      (Staff)")
        self.stdout.write("  auditor / password123    (Auditor — read-only)")
        self.stdout.write("  planner / password123    (Production Planner)")
        self.stdout.write("  supervisor / password123 (Floor Supervisor)")
        self.stdout.write("  technician / password123 (Technician)")

    def _create_users(self):
        defaults = {
            "admin": ("admin", True),
            "manager": ("manager", False),
            "staff": ("staff", False),
            "auditor": ("auditor", False),
            "planner": ("planner", False),
            "supervisor": ("supervisor", False),
            "technician": ("technician", False),
        }
        for username, (role, is_super) in defaults.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "email": f"{username}@inventory.local",
                    "is_staff": is_super,
                    "is_superuser": is_super,
                    "first_name": username.capitalize(),
                },
            )
            if created:
                user.set_password("password123")
                user.save()
                self.stdout.write(f"  + user {username} ({role})")

    def _create_categories(self):
        objs = []
        for name, desc in CATEGORIES:
            cat, _ = Category.objects.get_or_create(name=name, defaults={"description": desc})
            objs.append(cat)
        self.stdout.write(f"  + {len(objs)} categories")
        return objs

    def _create_suppliers(self):
        objs = []
        for name, contact, email, phone, gst in SUPPLIERS:
            sup, _ = Supplier.objects.get_or_create(
                name=name,
                defaults={"contact_person": contact, "email": email, "phone": phone, "gst_number": gst},
            )
            objs.append(sup)
        self.stdout.write(f"  + {len(objs)} suppliers")
        return objs

    def _create_products(self, categories):
        units = [Unit.PIECE, Unit.BOX, Unit.PACK, Unit.KILOGRAM, Unit.LITRE]
        products, counter = [], 1
        for cat in categories:
            for name in PRODUCT_NAMES[cat.name]:
                purchase = Decimal(random.randint(50, 800))
                product, created = Product.objects.get_or_create(
                    sku=f"SKU-{counter:04d}",
                    defaults={
                        "name": name,
                        "barcode": f"890{random.randint(1000000000, 9999999999)}",
                        "category": cat,
                        "unit": random.choice(units),
                        "purchase_price": purchase,
                        "selling_price": purchase * Decimal("1.35"),
                        "current_stock": 0,
                        "reorder_level": random.choice([5, 10, 15, 20]),
                        "status": ProductStatus.ACTIVE,
                        "description": f"{name} supplied in bulk.",
                    },
                )
                products.append(product)
                counter += 1
        self.stdout.write(f"  + {len(products)} products")
        return products

    def _create_transactions(self, products, count):
        staff = list(User.objects.all())
        now = timezone.now()
        created = 0
        # Opening stock for every product (only once — idempotent across re-runs)
        for product in products:
            if StockTransaction.objects.filter(
                product=product, reference_number="OPENING"
            ).exists():
                continue
            opening = random.randint(20, 120)
            txn = StockTransaction.objects.create(
                product=product,
                transaction_type=TransactionType.STOCK_IN,
                quantity=opening,
                reference_number="OPENING",
                notes="Opening stock",
                user=random.choice(staff),
            )
            # Backdate opening so it isn't all clustered on today.
            StockTransaction.objects.filter(pk=txn.pk).update(
                created_at=now - timedelta(days=random.randint(120, 180))
            )
            created += 1
        # Random historical movements — seeded once (idempotent across re-runs).
        if StockTransaction.objects.filter(reference_number__startswith="TXN-").exists():
            self.stdout.write(f"  + {created} stock transactions (historical already seeded)")
            return
        for _ in range(count):
            product = random.choice(products)
            ttype = random.choices(
                [TransactionType.STOCK_IN, TransactionType.STOCK_OUT, TransactionType.ADJUSTMENT],
                weights=[3, 5, 1],
            )[0]
            if ttype == TransactionType.STOCK_OUT:
                product.refresh_from_db()
                if product.current_stock <= 1:
                    continue
                qty = random.randint(1, min(product.current_stock, 15))
            elif ttype == TransactionType.ADJUSTMENT:
                qty = random.choice([-2, -1, 1, 2])
            else:
                qty = random.randint(5, 40)
            txn = StockTransaction(
                product=product, transaction_type=ttype, quantity=qty,
                reference_number=f"TXN-{random.randint(1000, 9999)}",
                user=random.choice(staff),
            )
            txn.save()
            # Backdate for chart history
            StockTransaction.objects.filter(pk=txn.pk).update(
                created_at=now - timedelta(days=random.randint(0, 165))
            )
            created += 1
        self.stdout.write(f"  + {created} stock transactions")

    def _create_purchases(self, suppliers, products):
        created = 0
        for i in range(1, 6):
            order, made = PurchaseOrder.objects.get_or_create(
                po_number=f"PO-2026-{i:03d}",
                defaults={
                    "supplier": random.choice(suppliers),
                    "status": random.choice([PurchaseStatus.ORDERED, PurchaseStatus.DRAFT]),
                    "created_by": User.objects.filter(role="manager").first() or User.objects.first(),
                },
            )
            if not made:
                continue
            for product in random.sample(products, k=random.randint(2, 4)):
                PurchaseItem.objects.get_or_create(
                    purchase_order=order, product=product,
                    defaults={"quantity": random.randint(10, 60), "unit_price": product.purchase_price},
                )
            order.recalculate_total()
            created += 1
        self.stdout.write(f"  + {created} purchase orders")

    def _create_production(self, products):
        """Seed a sample Bill of Materials and a draft work order."""
        from production.models import BOMComponent, WorkOrder, WorkOrderType
        from products.models import Product

        by_name = {p.name: p for p in products}
        finished = by_name.get("Bluetooth Speaker")
        comps = [
            (by_name.get("USB-C Cable"), 1),
            (by_name.get("HDMI Adapter"), 1),
            (by_name.get("Power Bank 10000mAh"), 1),
        ]
        if not finished or any(c is None for c, _ in comps):
            return
        for component, qty in comps:
            BOMComponent.objects.get_or_create(
                product=finished, component=component, defaults={"quantity": qty}
            )
        if not WorkOrder.objects.filter(wo_number="SWO-2026-001").exists():
            planner = User.objects.filter(role="planner").first()
            wo = WorkOrder.objects.create(
                wo_number="SWO-2026-001",
                product=finished,
                quantity=5,
                wo_type=WorkOrderType.ASSEMBLY,
                created_by=planner,
                notes="Sample assembly work order — release, assign and complete to test.",
            )
            wo.build_components_from_bom()
        self.stdout.write("  + 1 bill of materials + 1 sample work order")
