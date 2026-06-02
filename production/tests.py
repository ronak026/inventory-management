"""Tests for the work-order (SWO) lifecycle and BOM reservations."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from products.models import Category, Product
from .models import BOMComponent, WorkOrder, WorkOrderStatus, WorkOrderType

User = get_user_model()


class WorkOrderLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("plan", password="x", role="planner")
        cat = Category.objects.create(name="Cat")

        def mk(name, sku, stock):
            return Product.objects.create(
                name=name, sku=sku, category=cat,
                purchase_price=Decimal("1"), selling_price=Decimal("2"),
                current_stock=stock,
            )

        self.finished = mk("Widget", "W", 0)
        self.bolt = mk("Bolt", "B", 100)
        self.nut = mk("Nut", "N", 100)
        BOMComponent.objects.create(product=self.finished, component=self.bolt, quantity=2)
        BOMComponent.objects.create(product=self.finished, component=self.nut, quantity=4)

        self.wo = WorkOrder.objects.create(
            wo_number="WO-1", product=self.finished, quantity=10,
            wo_type=WorkOrderType.ASSEMBLY, created_by=self.user,
        )
        self.wo.build_components_from_bom()

    def test_components_built_from_bom(self):
        # 10 units x (2 bolts, 4 nuts)
        reqs = {c.component.name: c.required_quantity for c in self.wo.components.all()}
        self.assertEqual(reqs, {"Bolt": 20, "Nut": 40})

    def test_release_reserves_stock(self):
        ok, _ = self.wo.release(user=self.user)
        self.assertTrue(ok)
        self.wo.refresh_from_db()
        self.bolt.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrderStatus.RELEASED)
        self.assertEqual(self.bolt.reserved_stock, 20)
        self.assertEqual(self.bolt.available_stock, 80)  # 100 - 20

    def test_release_blocks_on_shortage(self):
        self.bolt.current_stock = 5  # need 20
        self.bolt.save()
        ok, msg = self.wo.release(user=self.user)
        self.assertFalse(ok)
        self.assertIn("Bolt", msg)
        self.bolt.refresh_from_db()
        self.assertEqual(self.bolt.reserved_stock, 0)

    def test_complete_consumes_and_produces(self):
        self.wo.release(user=self.user)
        self.wo.start(user=self.user)
        ok, _ = self.wo.complete(user=self.user)
        self.assertTrue(ok)
        self.bolt.refresh_from_db(); self.nut.refresh_from_db(); self.finished.refresh_from_db()
        self.assertEqual(self.bolt.current_stock, 80)   # 100 - 20 consumed
        self.assertEqual(self.nut.current_stock, 60)    # 100 - 40 consumed
        self.assertEqual(self.bolt.reserved_stock, 0)   # reservation released
        self.assertEqual(self.finished.current_stock, 10)  # produced
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrderStatus.COMPLETED)

    def test_cancel_releases_reservation(self):
        self.wo.release(user=self.user)
        self.bolt.refresh_from_db()
        self.assertEqual(self.bolt.reserved_stock, 20)
        self.wo.cancel(user=self.user)
        self.bolt.refresh_from_db()
        self.assertEqual(self.bolt.reserved_stock, 0)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrderStatus.CANCELLED)

    def test_service_order_consumes_but_produces_nothing(self):
        self.wo.wo_type = WorkOrderType.SERVICE
        self.wo.save()
        self.wo.release(user=self.user)
        self.wo.complete(user=self.user)
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.current_stock, 0)  # no finished stock produced


class ReservedLowStockTests(TestCase):
    def test_reserved_stock_counts_against_low_stock(self):
        cat = Category.objects.create(name="C")
        p = Product.objects.create(
            name="P", sku="P1", category=cat, purchase_price=Decimal("1"),
            selling_price=Decimal("2"), current_stock=12, reorder_level=10,
        )
        self.assertFalse(p.is_low_stock)        # available 12 > 10
        p.reserved_stock = 5
        p.save()
        self.assertTrue(p.is_low_stock)         # available 7 <= 10
        self.assertIn(p, Product.objects.low_stock())
