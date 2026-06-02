"""End-to-end QA suite mapped to the manual test checklist.

Run:  python manage.py test inventory.tests_qa -v 2

Covers Suite 4 (stock transactions), 5 (purchases), 6 (production),
7 (reports), 9 (role permissions) and 10 (API). Each test is isolated
(test DB) and builds its own fixtures.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from inventory.forms import StockTransactionForm
from inventory.models import StockTransaction, TransactionType
from products.models import Category, Product
from purchases.forms import PurchaseItemFormSet
from purchases.models import PurchaseOrder, PurchaseStatus
from suppliers.models import Supplier
from production.models import BOMComponent, WorkOrder, WorkOrderStatus, WorkOrderType

User = get_user_model()
PWD = "password123"


class QABase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.roles = {}
        for r in ["admin", "manager", "staff", "auditor", "planner", "supervisor", "technician"]:
            cls.roles[r] = User.objects.create_user(
                r, password=PWD, role=r,
                is_superuser=(r == "admin"), is_staff=(r == "admin"),
            )
        cls.cat = Category.objects.create(name="QA Cat")
        cls.supplier = Supplier.objects.create(name="QA Supplier")

        def mk(name, sku, stock, reorder=10):
            return Product.objects.create(
                name=name, sku=sku, category=cls.cat, purchase_price=Decimal("10"),
                selling_price=Decimal("15"), current_stock=stock, reorder_level=reorder,
            )

        cls.widget = mk("QA Widget", "QW", 0)        # finished good
        cls.bolt = mk("QA Bolt", "QB", 100)          # component
        cls.nut = mk("QA Nut", "QN", 100)            # component
        cls.gadget = mk("QA Gadget", "QG", 50)       # plain sellable
        BOMComponent.objects.create(product=cls.widget, component=cls.bolt, quantity=2)
        BOMComponent.objects.create(product=cls.widget, component=cls.nut, quantity=3)

    def login(self, role):
        self.client.force_login(self.roles[role])


# --- Suite 4: Stock transactions --------------------------------------------
class Suite4_StockTransactions(QABase):
    def test_4_1_stock_in_increases(self):
        StockTransaction.objects.create(product=self.gadget, transaction_type=TransactionType.STOCK_IN, quantity=10)
        self.gadget.refresh_from_db()
        self.assertEqual(self.gadget.current_stock, 60)

    def test_4_2_stock_out_blocked_over_onhand(self):
        form = StockTransactionForm(data={
            "product": self.gadget.id, "transaction_type": "out", "quantity": 9999,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_4_3_adjustment_signed_delta(self):
        StockTransaction.objects.create(product=self.gadget, transaction_type=TransactionType.ADJUSTMENT, quantity=-3)
        self.gadget.refresh_from_db()
        self.assertEqual(self.gadget.current_stock, 47)

    def test_4_4_history_snapshot(self):
        t = StockTransaction.objects.create(product=self.gadget, transaction_type=TransactionType.STOCK_IN, quantity=5)
        self.assertEqual(t.quantity_change, 5)
        self.assertEqual(t.resulting_stock, 55)


# --- Suite 5: Purchases ------------------------------------------------------
class Suite5_Purchases(QABase):
    def _po_payload(self, n_items, number="QA-PO-1"):
        prefix = PurchaseItemFormSet().prefix
        prods = [self.bolt, self.nut, self.gadget, self.widget][:n_items]
        data = {
            "po_number": number, "supplier": self.supplier.id, "status": "ordered",
            "order_date": "2026-06-01", "expected_date": "2026-06-08", "notes": "qa",
            f"{prefix}-TOTAL_FORMS": str(n_items), f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "1", f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for i, p in enumerate(prods):
            data[f"{prefix}-{i}-product"] = p.id
            data[f"{prefix}-{i}-quantity"] = 10
            data[f"{prefix}-{i}-unit_price"] = "10"
        return data

    def test_5_1_add_more_than_three_items(self):
        self.login("manager")
        self.client.post("/purchases/add/", self._po_payload(4))
        po = PurchaseOrder.objects.get(po_number="QA-PO-1")
        self.assertEqual(po.items.count(), 4)

    def test_5_2_total_auto_calculated(self):
        self.login("manager")
        self.client.post("/purchases/add/", self._po_payload(2, "QA-PO-2"))
        po = PurchaseOrder.objects.get(po_number="QA-PO-2")
        self.assertEqual(po.total_amount, Decimal("200"))  # 2 x (10 x 10)

    def test_5_4_partial_then_full_receive(self):
        self.login("manager")
        po = PurchaseOrder.objects.create(po_number="QA-PO-3", supplier=self.supplier, status=PurchaseStatus.ORDERED)
        from purchases.models import PurchaseItem
        item = PurchaseItem.objects.create(purchase_order=po, product=self.gadget, quantity=20, unit_price=Decimal("10"))
        start = self.gadget.current_stock
        # partial
        self.client.post(f"/purchases/{po.pk}/receive/", {f"qty_{item.id}": "5"})
        po.refresh_from_db(); item.refresh_from_db(); self.gadget.refresh_from_db()
        self.assertEqual(item.received_quantity, 5)
        self.assertEqual(po.status, PurchaseStatus.PARTIAL)
        self.assertEqual(self.gadget.current_stock, start + 5)
        # remainder
        self.client.post(f"/purchases/{po.pk}/receive/", {"receive_all": "1"})
        po.refresh_from_db(); self.gadget.refresh_from_db()
        self.assertEqual(po.status, PurchaseStatus.RECEIVED)
        self.assertEqual(self.gadget.current_stock, start + 20)

    def test_5_6_invoice_pdf(self):
        self.login("manager")
        po = PurchaseOrder.objects.create(po_number="QA-PO-INV", supplier=self.supplier, status=PurchaseStatus.ORDERED)
        from purchases.models import PurchaseItem
        PurchaseItem.objects.create(purchase_order=po, product=self.gadget, quantity=3, unit_price=Decimal("10"))
        po.recalculate_total()
        resp = self.client.get(f"/purchases/{po.pk}/invoice/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertGreater(len(resp.content), 1000)


# --- Suite 6: Production / Work Orders ---------------------------------------
class Suite6_Production(QABase):
    def _create_wo(self):
        wo = WorkOrder.objects.create(
            wo_number="QA-WO-1", product=self.widget, quantity=10,
            wo_type=WorkOrderType.ASSEMBLY, created_by=self.roles["planner"])
        wo.build_components_from_bom()
        return wo

    def test_6_2_planner_create_builds_components(self):
        self.login("planner")
        self.client.post("/production/add/", {
            "wo_number": "QA-WO-2", "product": self.widget.id, "quantity": 5,
            "wo_type": "assembly", "notes": "qa"})
        wo = WorkOrder.objects.get(wo_number="QA-WO-2")
        self.assertEqual(wo.components.count(), 2)

    def test_6_3_release_reserves(self):
        wo = self._create_wo()
        ok, _ = wo.release(user=self.roles["planner"])
        self.bolt.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(self.bolt.reserved_stock, 20)

    def test_6_6_full_flow_moves_stock(self):
        wo = self._create_wo()
        self.login("planner"); self.client.post(f"/production/{wo.pk}/release/")
        self.login("supervisor"); self.client.post(f"/production/{wo.pk}/assign/", {"assigned_to": self.roles["technician"].id})
        self.login("technician")
        self.client.post(f"/production/{wo.pk}/start/")
        self.client.post(f"/production/{wo.pk}/complete/")
        wo.refresh_from_db(); self.bolt.refresh_from_db(); self.widget.refresh_from_db()
        self.assertEqual(wo.status, WorkOrderStatus.COMPLETED)
        self.assertEqual(self.bolt.current_stock, 80)   # 100 - 20
        self.assertEqual(self.bolt.reserved_stock, 0)
        self.assertEqual(self.widget.current_stock, 10)  # produced

    def test_6_7_cancel_releases(self):
        wo = self._create_wo()
        wo.release(user=self.roles["planner"])
        wo.cancel(user=self.roles["planner"])
        self.bolt.refresh_from_db()
        self.assertEqual(self.bolt.reserved_stock, 0)


# --- Suite 7: Reports --------------------------------------------------------
class Suite7_Reports(QABase):
    def setUp(self):
        from datetime import timedelta
        now = timezone.now()
        self.recent = StockTransaction.objects.create(product=self.gadget, transaction_type=TransactionType.STOCK_IN, quantity=10)
        old = StockTransaction.objects.create(product=self.gadget, transaction_type=TransactionType.STOCK_OUT, quantity=2)
        StockTransaction.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=60))

    def test_7_1_period_filter(self):
        from reports.datasets import stock_movement_report
        self.assertEqual(len(stock_movement_report({"period": "7"})[2]), 1)
        self.assertEqual(len(stock_movement_report({"period": "90"})[2]), 2)

    def test_7_2_type_filter(self):
        from reports.datasets import stock_movement_report
        self.assertEqual(len(stock_movement_report({"period": "90", "type": "in"})[2]), 1)

    def test_7_4_serial_column_first(self):
        self.login("admin")
        html = self.client.get("/reports/inventory/").content.decode()
        self.assertIn(">No.<", html)

    def test_7_5_export_matches_filter(self):
        self.login("admin")
        csv = self.client.get("/reports/stock-movement/export/csv/?period=7&type=in").content.decode()
        self.assertIn("Stock In", csv)
        self.assertNotIn("Stock Out", csv)


# --- Suite 9: Role permission matrix ----------------------------------------
class Suite9_Permissions(QABase):
    def assert_status(self, role, url, expected, method="get", data=None):
        self.login(role)
        resp = getattr(self.client, method)(url, data or {})
        self.assertEqual(resp.status_code, expected, f"{role} {method} {url}")
        self.client.logout()

    def test_9_1_staff_cannot_create_master_data(self):
        for url in ["/products/add/", "/suppliers/add/", "/purchases/add/", "/production/add/"]:
            self.assert_status("staff", url, 403)

    def test_9_1_staff_can_record_transactions(self):
        self.assert_status("staff", "/transactions/add/", 200)

    def test_9_2_auditor_readonly(self):
        self.assert_status("auditor", "/products/", 200)          # view ok
        self.assert_status("auditor", "/transactions/add/", 403)  # no writes
        self.assert_status("auditor", "/products/add/", 403)
        self.assert_status("auditor", "/activity/", 200)          # can view audit

    def test_9_3_planner_creates_not_assigns(self):
        self.assert_status("planner", "/production/add/", 200)
        wo = WorkOrder.objects.create(wo_number="QA-WO-P", product=self.widget, quantity=1, created_by=self.roles["planner"])
        self.assert_status("planner", f"/production/{wo.pk}/assign/", 403, method="post",
                           data={"assigned_to": self.roles["technician"].id})

    def test_9_4_supervisor_assigns_not_creates(self):
        self.assert_status("supervisor", "/production/add/", 403)

    def test_9_5_technician_cannot_create(self):
        self.assert_status("technician", "/production/add/", 403)

    def test_9_6_manager_no_user_admin(self):
        self.assert_status("manager", "/products/add/", 200)
        self.assert_status("manager", "/accounts/users/", 403)

    def test_9_7_admin_full_access(self):
        self.assert_status("admin", "/accounts/users/", 200)


# --- Suite 10: API -----------------------------------------------------------
class Suite10_Api(QABase):
    def _token_client(self, role):
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=self.roles[role])
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return c

    def test_10_2_products_list_and_filter(self):
        c = self._token_client("manager")
        self.assertEqual(c.get("/api/products/").status_code, 200)
        self.assertEqual(c.get("/api/products/low_stock/").status_code, 200)

    def test_10_3_auditor_write_forbidden(self):
        c = self._token_client("auditor")
        self.assertEqual(c.get("/api/products/").status_code, 200)
        resp = c.post("/api/products/", {
            "name": "x", "sku": "x9", "category": self.cat.id, "unit": "pcs",
            "purchase_price": "1", "selling_price": "1", "reorder_level": 1, "status": "active"})
        self.assertEqual(resp.status_code, 403)

    def test_10_3_staff_can_post_transaction(self):
        c = self._token_client("staff")
        resp = c.post("/api/transactions/", {
            "product": self.gadget.id, "transaction_type": "in", "quantity": 1})
        self.assertEqual(resp.status_code, 201)


# --- Suite 1: Authentication & profile --------------------------------------
class Suite1_Auth(QABase):
    def test_1_1_valid_login_redirects_to_dashboard(self):
        resp = self.client.post("/accounts/login/", {"username": "staff", "password": PWD})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/")

    def test_1_2_invalid_login_rejected(self):
        resp = self.client.post("/accounts/login/", {"username": "staff", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)        # re-rendered with error
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_1_3_logout_redirects_to_login(self):
        self.login("staff")
        resp = self.client.post("/accounts/logout/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_1_4_password_reset_sends_email(self):
        from django.core import mail
        u = self.roles["staff"]; u.email = "staff@example.com"; u.save()
        resp = self.client.post("/accounts/password-reset/", {"email": "staff@example.com"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset", mail.outbox[0].body.lower())

    def test_1_5_change_password(self):
        self.login("staff")
        resp = self.client.post("/accounts/password-change/", {
            "old_password": PWD, "new_password1": "BrandNew123!", "new_password2": "BrandNew123!"})
        self.assertEqual(resp.status_code, 302)
        self.client.logout()
        self.assertTrue(self.client.login(username="staff", password="BrandNew123!"))

    def test_1_6_edit_profile(self):
        self.login("staff")
        resp = self.client.post("/accounts/profile/edit/", {
            "first_name": "Updated", "last_name": "Name", "email": "s@x.com",
            "phone": "12345", "job_title": "Picker", "address": "Aisle 5"})
        self.assertEqual(resp.status_code, 302)
        self.roles["staff"].refresh_from_db()
        self.assertEqual(self.roles["staff"].first_name, "Updated")

    def test_1_7_register_creates_inactive_staff(self):
        resp = self.client.post("/accounts/register/", {
            "username": "newbie", "first_name": "New", "last_name": "Bie",
            "email": "newbie@x.com", "password1": "BrandNew123!", "password2": "BrandNew123!"})
        self.assertEqual(resp.status_code, 302)
        u = User.objects.get(username="newbie")
        self.assertFalse(u.is_active)        # pending approval
        self.assertEqual(u.role, "staff")    # role forced, not user-chosen

    def test_1_8_inactive_cannot_login(self):
        self.client.post("/accounts/register/", {
            "username": "newbie2", "first_name": "N", "last_name": "B",
            "email": "n2@x.com", "password1": "BrandNew123!", "password2": "BrandNew123!"})
        self.assertFalse(self.client.login(username="newbie2", password="BrandNew123!"))

    def test_1_9_admin_approve_then_login(self):
        self.client.post("/accounts/register/", {
            "username": "newbie3", "first_name": "N", "last_name": "B",
            "email": "n3@x.com", "password1": "BrandNew123!", "password2": "BrandNew123!"})
        u = User.objects.get(username="newbie3")
        self.login("manager")  # non-admin cannot approve
        self.assertEqual(self.client.post(f"/accounts/users/{u.pk}/approve/").status_code, 403)
        self.client.logout()
        self.login("admin")    # admin approves
        self.client.post(f"/accounts/users/{u.pk}/approve/")
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        self.client.logout()
        self.assertTrue(self.client.login(username="newbie3", password="BrandNew123!"))

    def test_1_10_registration_emails_admins_and_badges(self):
        from django.core import mail
        # Give the admin an email so a notification can be sent.
        self.roles["admin"].email = "admin@example.com"; self.roles["admin"].save()
        self.client.post("/accounts/register/", {
            "username": "newbie4", "first_name": "N", "last_name": "B",
            "email": "n4@x.com", "password1": "BrandNew123!", "password2": "BrandNew123!"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("admin@example.com", mail.outbox[0].to)
        self.assertIn("approval", mail.outbox[0].subject.lower())
        # Admin sees the pending-count badge in context.
        self.login("admin")
        self.assertGreaterEqual(self.client.get("/").context["pending_user_count"], 1)


# --- Suite 8: Dashboard, search, audit, notifications -----------------------
class Suite8_DashboardSearch(QABase):
    def test_8_1_dashboard_charts_are_valid_objects(self):
        import json, re
        self.login("admin")
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total_products", resp.context)
        html = resp.content.decode()
        raw = re.search(r'id="chart-data"[^>]*>(.*?)</script>', html, re.S).group(1)
        data = json.loads(raw)
        self.assertIsInstance(data, dict)               # not a double-encoded string
        self.assertIn("stock_in", data)

    def test_8_2_low_stock_notification(self):
        # gadget reorder 10; drive available below it.
        Product.objects.filter(pk=self.gadget.pk).update(current_stock=2)
        self.login("admin")
        resp = self.client.get("/")
        self.assertGreaterEqual(resp.context["low_stock_total"], 1)

    def test_8_3_global_search_finds_records(self):
        self.login("admin")
        html = self.client.get("/search/?q=QA Widget").content.decode()
        self.assertIn("QA Widget", html)
        html2 = self.client.get("/search/?q=QA Supplier").content.decode()
        self.assertIn("QA Supplier", html2)

    def test_8_4_activity_log_records_user(self):
        from audit.models import ActivityLog
        self.login("manager")
        self.client.post("/products/categories/add/", {"name": "QA Logged", "description": ""})
        log = ActivityLog.objects.filter(object_repr__icontains="QA Logged").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, "created")
        self.assertEqual(log.user, self.roles["manager"])
