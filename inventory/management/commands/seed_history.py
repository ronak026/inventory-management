"""Generate time-distributed history so the report date filters have data.

Adds stock transactions and purchase orders spread across the past N months,
with back-dated timestamps, so the Stock Movement and Purchase reports return
meaningful results for any date range you pick.

Usage:
    python manage.py seed_history                 # last 6 months
    python manage.py seed_history --months 12     # last 12 months
    python manage.py seed_history --per-month 20 --pos-per-month 3

Run `seed_data` first so products, suppliers and users exist.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventory.models import StockTransaction, TransactionType
from products.models import Product
from purchases.models import PurchaseItem, PurchaseOrder, PurchaseStatus
from suppliers.models import Supplier

User = get_user_model()


class Command(BaseCommand):
    help = "Add time-distributed stock transactions and purchase orders across past months."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=6,
                            help="How many months back to spread data over.")
        parser.add_argument("--per-month", type=int, default=15,
                            help="Stock transactions to create per month.")
        parser.add_argument("--pos-per-month", type=int, default=2,
                            help="Purchase orders to create per month.")

    @transaction.atomic
    def handle(self, *args, **opts):
        products = list(Product.objects.all())
        suppliers = list(Supplier.objects.all())
        users = list(User.objects.all())
        if not products or not suppliers:
            self.stderr.write(self.style.ERROR(
                "No products/suppliers found. Run `python manage.py seed_data` first."))
            return

        months = opts["months"]
        now = timezone.now()
        tx_count = 0
        po_count = 0

        for m in range(months):
            base_days = m * 30  # window for "m months ago"

            # --- Stock transactions spread through the month ------------------
            for _ in range(opts["per_month"]):
                dt = now - timedelta(
                    days=base_days + random.randint(0, 29),
                    hours=random.randint(0, 23), minutes=random.randint(0, 59),
                )
                product = random.choice(products)
                product.refresh_from_db()

                ttype = random.choices(
                    [TransactionType.STOCK_IN, TransactionType.STOCK_OUT, TransactionType.ADJUSTMENT],
                    weights=[4, 5, 1],
                )[0]
                if ttype == TransactionType.STOCK_OUT and product.current_stock <= 1:
                    ttype = TransactionType.STOCK_IN

                if ttype == TransactionType.STOCK_IN:
                    qty = random.randint(5, 40)
                elif ttype == TransactionType.STOCK_OUT:
                    qty = random.randint(1, min(product.current_stock, 12))
                else:
                    qty = random.choice([-2, -1, 1, 2])
                    if product.current_stock + qty < 0:
                        qty = abs(qty)

                txn = StockTransaction(
                    product=product, transaction_type=ttype, quantity=qty,
                    reference_number=f"HX-{dt:%y%m}-{random.randint(100, 999)}",
                    user=random.choice(users) if users else None,
                )
                txn.save()
                # Back-date the auto_now_add timestamp into this month.
                StockTransaction.objects.filter(pk=txn.pk).update(created_at=dt)
                tx_count += 1

            # --- Purchase orders dated within the month -----------------------
            for i in range(opts["pos_per_month"]):
                dt = now - timedelta(days=base_days + random.randint(0, 28))
                order_date = dt.date()
                intended = random.choices(
                    ["received", "ordered", "draft"], weights=[3, 2, 1])[0]
                initial_status = (
                    PurchaseStatus.DRAFT if intended == "draft" else PurchaseStatus.ORDERED
                )
                po = PurchaseOrder.objects.create(
                    po_number=f"PO-{order_date:%Y%m}-{m}{i}{random.randint(10, 99)}",
                    supplier=random.choice(suppliers),
                    order_date=order_date,
                    expected_date=order_date + timedelta(days=7),
                    status=initial_status,
                    created_by=random.choice(users) if users else None,
                )
                for product in random.sample(products, k=random.randint(2, 4)):
                    PurchaseItem.objects.create(
                        purchase_order=po, product=product,
                        quantity=random.randint(10, 50),
                        unit_price=product.purchase_price,
                    )
                po.recalculate_total()

                if intended == "received":
                    # receive_stock() requires a non-received status (set above).
                    po.receive_stock(user=po.created_by)
                    # Back-date the generated stock-in movements and receipt time.
                    StockTransaction.objects.filter(source_purchase=po).update(created_at=dt)
                    PurchaseOrder.objects.filter(pk=po.pk).update(received_at=dt)
                po_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Added {tx_count} stock transactions and {po_count} purchase orders "
            f"spread across the last {months} months."))
        self.stdout.write(
            "Try the date filters on /reports/stock-movement/ and /reports/purchase/.")
