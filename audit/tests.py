"""Tests for the activity/audit log."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from products.models import Category, Product
from .models import ActivityLog

User = get_user_model()


class ActivityLogTests(TestCase):
    def test_create_update_delete_are_logged(self):
        cat = Category.objects.create(name="Logged Cat")
        log = ActivityLog.objects.filter(model_name__iexact="Category").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, "created")
        self.assertIn("Logged Cat", log.object_repr)

        cat.name = "Renamed"
        cat.save()
        self.assertTrue(
            ActivityLog.objects.filter(model_name__iexact="Category", action="updated").exists()
        )

        cat.delete()
        self.assertTrue(
            ActivityLog.objects.filter(model_name__iexact="Category", action="deleted").exists()
        )

    def test_product_change_logged(self):
        cat = Category.objects.create(name="C")
        before = ActivityLog.objects.count()
        Product.objects.create(
            name="Tracked", sku="T1", category=cat,
            purchase_price=Decimal("1"), selling_price=Decimal("2"),
        )
        self.assertGreater(ActivityLog.objects.count(), before)


class ActivityLogAccessTests(TestCase):
    def setUp(self):
        for role in ["admin", "manager", "auditor", "staff"]:
            User.objects.create_user(role, password="x", role=role)

    def test_access_matrix(self):
        # Admin / Manager / Auditor allowed; Staff forbidden.
        for role, expected in [("admin", 200), ("manager", 200), ("auditor", 200), ("staff", 403)]:
            self.client.login(username=role, password="x")
            self.assertEqual(self.client.get("/activity/").status_code, expected, role)
            self.client.logout()
