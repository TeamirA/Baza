from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import Product
from ..templatetags.money import money


class MoneyFilterTests(SimpleTestCase):
    def test_formats_with_thousands_separator(self):
        self.assertEqual(money(Decimal("1999.9")), "1,999.90")
        self.assertEqual(money(Decimal("9.99")), "9.99")
        self.assertEqual(money(None), "")


class PriceDisplayTests(TestCase):
    def test_card_page_and_suggestions_use_separators(self):
        laptop = Product.objects.create(name="Big Laptop", price=Decimal("1999.99"), stock=3)
        self.assertContains(self.client.get(reverse("products:list")), "$1,999.99")
        self.assertContains(self.client.get(laptop.get_absolute_url()), "$1,999.99")
        self.assertEqual(self.client.get(reverse("products:suggest"), {"q": "laptop"}).json()["results"][0]["price"], "1,999.99")
