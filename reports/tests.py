"""Tests for report date presets and movement-type filtering."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from inventory.models import StockTransaction, TransactionType
from products.models import Category, Product
from .datasets import date_bounds, stock_movement_report

User = get_user_model()


class DateBoundsTests(TestCase):
    def test_presets_resolve_ranges(self):
        today = timezone.localdate()
        self.assertEqual(date_bounds({"period": "7"}), (today - timedelta(days=6), today))
        self.assertEqual(date_bounds({"period": "30"}), (today - timedelta(days=29), today))
        self.assertEqual(date_bounds({"period": "month"}), (today.replace(day=1), today))
        self.assertEqual(date_bounds({}), (None, None))

    def test_explicit_dates(self):
        s, e = date_bounds({"start": "2026-01-01", "end": "2026-01-31"})
        self.assertEqual((s.isoformat(), e.isoformat()), ("2026-01-01", "2026-01-31"))


class StockMovementReportTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name="C")
        self.user = User.objects.create_user("u", password="x")
        self.product = Product.objects.create(
            name="P", sku="P1", category=cat,
            purchase_price=Decimal("1"), selling_price=Decimal("2"), current_stock=0,
        )
        now = timezone.now()
        # one recent stock-in, one old stock-out
        recent = StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN,
            quantity=50, user=self.user)
        old = StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_OUT,
            quantity=5, user=self.user)
        StockTransaction.objects.filter(pk=old.pk).update(
            created_at=now - timedelta(days=60))

    def test_period_filters_out_old_rows(self):
        _, _, rows7 = stock_movement_report({"period": "7"})
        _, _, rows90 = stock_movement_report({"period": "90"})
        self.assertEqual(len(rows7), 1)   # only the recent one
        self.assertEqual(len(rows90), 2)  # both within 90 days

    def test_type_filter(self):
        _, _, ins = stock_movement_report({"period": "90", "type": "in"})
        _, _, outs = stock_movement_report({"period": "90", "type": "out"})
        self.assertEqual(len(ins), 1)
        self.assertEqual(len(outs), 1)


class ReportSerialColumnTests(TestCase):
    def test_serial_column_prepended(self):
        User.objects.create_user("admin2", password="x", role="admin", is_superuser=True, is_staff=True)
        self.client.login(username="admin2", password="x")
        html = self.client.get("/reports/inventory/").content.decode()
        # 'No.' header should appear before the first real column header.
        self.assertIn(">No.<", html)
