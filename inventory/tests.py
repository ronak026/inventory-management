"""Tests for stock-movement logic — the system's core invariant."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import StockTransaction, TransactionType
from products.models import Category, Product
from purchases.models import PurchaseItem, PurchaseOrder, PurchaseStatus
from suppliers.models import Supplier

User = get_user_model()


class StockTransactionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="x")
        self.category = Category.objects.create(name="Test Cat")
        self.product = Product.objects.create(
            name="Widget", sku="W-1", category=self.category,
            purchase_price=Decimal("10"), selling_price=Decimal("15"),
            current_stock=0, reorder_level=5,
        )

    def test_stock_in_increases_stock(self):
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN,
            quantity=20, user=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 20)

    def test_stock_out_decreases_stock(self):
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN, quantity=20)
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_OUT, quantity=8)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 12)

    def test_adjustment_applies_signed_delta(self):
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN, quantity=10)
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.ADJUSTMENT, quantity=-3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 7)

    def test_resulting_stock_snapshot_recorded(self):
        txn = StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN, quantity=5)
        self.assertEqual(txn.resulting_stock, 5)
        self.assertEqual(txn.quantity_change, 5)

    def test_low_stock_property(self):
        self.assertTrue(self.product.is_low_stock)  # 0 <= 5
        StockTransaction.objects.create(
            product=self.product, transaction_type=TransactionType.STOCK_IN, quantity=10)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_low_stock)


class PurchaseReceiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer", password="x", role="manager")
        self.supplier = Supplier.objects.create(name="ACME")
        self.category = Category.objects.create(name="Parts")
        self.product = Product.objects.create(
            name="Bolt", sku="B-1", category=self.category,
            purchase_price=Decimal("2"), selling_price=Decimal("3"), current_stock=0,
        )
        self.po = PurchaseOrder.objects.create(
            po_number="PO-1", supplier=self.supplier, status=PurchaseStatus.ORDERED,
            created_by=self.user,
        )
        PurchaseItem.objects.create(
            purchase_order=self.po, product=self.product, quantity=50,
            unit_price=Decimal("2"),
        )
        self.po.recalculate_total()

    def test_total_amount_calculated(self):
        self.assertEqual(self.po.total_amount, Decimal("100"))

    def test_receive_updates_inventory_once(self):
        self.po.receive_stock(user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 50)
        self.assertEqual(self.po.status, PurchaseStatus.RECEIVED)

        # Receiving again must be idempotent (no double counting).
        self.po.receive_stock(user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 50)
