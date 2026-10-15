from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Product, StockMovement

User = get_user_model()

PRODUCTS = "/api/products/"


def make_product(owner, sku="SKU1", name="Item", price="100", quantity=0, reorder_level=5):
    return Product.objects.create(
        owner=owner,
        name=name,
        sku=sku,
        price=Decimal(price),
        quantity=quantity,
        reorder_level=reorder_level,
    )


class ProductModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("njeri", password="pass12345")
        self.product = make_product(self.user)

    def test_adjust_stock_adds_and_records_movement(self):
        movement = self.product.adjust_stock(10, "Delivery")
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)
        self.assertEqual(movement.change, 10)
        self.assertEqual(movement.quantity_after, 10)
        self.assertEqual(movement.reason, "Delivery")

    def test_adjust_stock_removes_stock(self):
        self.product.adjust_stock(10)
        self.product.adjust_stock(-4, "Sold")
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 6)
        self.assertEqual(self.product.movements.count(), 2)

    def test_cannot_remove_more_than_available(self):
        self.product.adjust_stock(3)
        with self.assertRaises(ValueError):
            self.product.adjust_stock(-4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        self.assertEqual(self.product.movements.count(), 1)

    def test_zero_change_is_rejected(self):
        with self.assertRaises(ValueError):
            self.product.adjust_stock(0)
        self.assertEqual(self.product.movements.count(), 0)

    def test_is_low_stock_at_or_below_reorder_level(self):
        low = make_product(self.user, sku="LOW", quantity=5, reorder_level=5)
        fine = make_product(self.user, sku="FINE", quantity=6, reorder_level=5)
        self.assertTrue(low.is_low_stock)
        self.assertFalse(fine.is_low_stock)


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_returns_token(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "demo", "password": "Str0ng-pass-99"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["username"], "demo")
        self.assertTrue(Token.objects.filter(key=response.data["token"]).exists())

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user("demo", password="pass12345")
        response = self.client.post(
            "/api/auth/register/",
            {"username": "Demo", "password": "Str0ng-pass-99"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "demo", "password": "12345678"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_token_login_returns_token(self):
        User.objects.create_user("demo", password="pass12345")
        response = self.client.post(
            "/api/auth/token/",
            {"username": "demo", "password": "pass12345"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_products_require_authentication(self):
        response = self.client.get(PRODUCTS)
        self.assertEqual(response.status_code, 401)


class ProductApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def create_via_api(self, **overrides):
        payload = {
            "name": "Unga 2kg",
            "sku": "unga-2kg",
            "price": "220.00",
            "reorder_level": 5,
        }
        payload.update(overrides)
        return self.client.post(PRODUCTS, payload, format="json")

    def test_create_normalises_sku_and_sets_owner(self):
        response = self.create_via_api(sku=" unga-2kg ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sku"], "UNGA-2KG")
        self.assertTrue(
            Product.objects.filter(sku="UNGA-2KG", owner=self.alice).exists()
        )

    def test_initial_quantity_creates_stock_and_history(self):
        response = self.create_via_api(initial_quantity=20)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["quantity"], 20)
        product = Product.objects.get(sku="UNGA-2KG")
        self.assertEqual(product.quantity, 20)
        self.assertEqual(product.movements.count(), 1)

    def test_duplicate_sku_for_same_user_rejected(self):
        self.create_via_api()
        response = self.create_via_api(sku="UNGA-2KG")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sku", response.data)

    def test_same_sku_allowed_for_different_users(self):
        make_product(self.bob, sku="UNGA-2KG")
        response = self.create_via_api()
        self.assertEqual(response.status_code, 201)

    def test_negative_price_rejected(self):
        response = self.create_via_api(price="-5")
        self.assertEqual(response.status_code, 400)
        self.assertIn("price", response.data)

    def test_user_sees_only_own_products(self):
        make_product(self.alice, sku="A1", name="Alice item")
        make_product(self.bob, sku="B1", name="Bob item")
        response = self.client.get(PRODUCTS)
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(names, ["Alice item"])

    def test_cannot_access_other_users_product(self):
        bobs = make_product(self.bob, sku="B1")
        url = f"{PRODUCTS}{bobs.pk}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.patch(url, {"name": "Hacked"}, format="json").status_code, 404
        )
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=bobs.pk).exists())

    def test_quantity_cannot_be_set_directly(self):
        product = make_product(self.alice, quantity=5)
        response = self.client.patch(
            f"{PRODUCTS}{product.pk}/", {"quantity": 999}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 5)

    def test_adjust_stock_endpoint(self):
        product = make_product(self.alice, quantity=10)
        response = self.client.post(
            f"{PRODUCTS}{product.pk}/adjust-stock/",
            {"change": -4, "reason": "Sold"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["quantity_after"], 6)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 6)

    def test_adjust_stock_rejects_overdraw_and_records_nothing(self):
        product = make_product(self.alice, quantity=3)
        response = self.client.post(
            f"{PRODUCTS}{product.pk}/adjust-stock/", {"change": -10}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Not enough stock", response.data["detail"])
        self.assertEqual(StockMovement.objects.count(), 0)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 3)

    def test_adjust_stock_rejects_zero(self):
        product = make_product(self.alice, quantity=3)
        response = self.client.post(
            f"{PRODUCTS}{product.pk}/adjust-stock/", {"change": 0}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("change", response.data)

    def test_history_lists_newest_first(self):
        product = make_product(self.alice)
        product.adjust_stock(10, "Delivery")
        product.adjust_stock(-3, "Sold")
        response = self.client.get(f"{PRODUCTS}{product.pk}/history/")
        self.assertEqual(response.status_code, 200)
        changes = [m["change"] for m in response.data["results"]]
        self.assertEqual(changes, [-3, 10])

    def test_low_stock_filter(self):
        make_product(self.alice, sku="LOW", name="Low item", quantity=2, reorder_level=5)
        make_product(self.alice, sku="OK", name="Fine item", quantity=50, reorder_level=5)
        response = self.client.get(PRODUCTS + "?low_stock=true")
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(names, ["Low item"])

    def test_search_by_name_or_sku(self):
        make_product(self.alice, sku="UNGA-1", name="Unga flour")
        make_product(self.alice, sku="OIL-1", name="Cooking oil")
        by_name = self.client.get(PRODUCTS + "?search=flour")
        by_sku = self.client.get(PRODUCTS + "?search=oil-1")
        self.assertEqual([p["sku"] for p in by_name.data["results"]], ["UNGA-1"])
        self.assertEqual([p["sku"] for p in by_sku.data["results"]], ["OIL-1"])

    def test_ordering_by_price(self):
        make_product(self.alice, sku="C", name="Cheap", price="10")
        make_product(self.alice, sku="E", name="Expensive", price="900")
        response = self.client.get(PRODUCTS + "?ordering=-price")
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(names, ["Expensive", "Cheap"])

    def test_results_are_paginated(self):
        Product.objects.bulk_create(
            [
                Product(owner=self.alice, name=f"Item {i:02d}", sku=f"P{i}", price=Decimal("1"))
                for i in range(12)
            ]
        )
        response = self.client.get(PRODUCTS)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])
