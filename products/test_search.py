from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .dtos import CategoryDTO, ProductDTO
from .models import Category, Product
from .search import correct, normalize, search


def dto(name, description="", category=None):
    return ProductDTO(
        id=hash(name), name=name, slug=name.lower().replace(" ", "-"), description=description,
        price=Decimal("1.00"), image_url="", stock=1,
        category=CategoryDTO(name=category, slug=category.lower()) if category else None, url="/",
    )


CATALOG = [
    dto("Canvas Tote Bag", "Sturdy canvas tote with an inner pocket.", "Accessories"),
    dto("Everyday Hoodie", "Brushed fleece hoodie with a kangaroo pocket.", "Apparel"),
    dto("Canvas Cap", "Six-panel washed canvas cap.", "Apparel"),
    dto("Ceramic Mug", "Stoneware mug, dishwasher safe.", "Home"),
    dto("Linen Throw Pillow", "Linen cover with a feather insert.", "Home"),
]


def names(results):
    return [p.name for p in results]


class SearchLogicTests(SimpleTestCase):
    def test_normalize_handles_case_accents_and_punctuation(self):
        self.assertEqual(normalize("Café-Mug, 350ML!"), ["cafe", "mug", "350ml"])

    def test_name_matches_rank_above_description_matches(self):
        # "pocket" is only in descriptions; "canvas" is in two names and one description.
        results, _ = search(CATALOG, "canvas")
        self.assertEqual(names(results), ["Canvas Tote Bag", "Canvas Cap"])
        results, _ = search(CATALOG, "pocket")
        self.assertEqual(names(results), ["Canvas Tote Bag", "Everyday Hoodie"])

    def test_every_word_must_match(self):
        results, _ = search(CATALOG, "canvas cap")
        self.assertEqual(names(results), ["Canvas Cap"])

    def test_category_and_prefix_matches(self):
        self.assertEqual(names(search(CATALOG, "appar")[0]), ["Everyday Hoodie", "Canvas Cap"])
        self.assertEqual(names(search(CATALOG, "hood")[0]), ["Everyday Hoodie"])

    def test_typos_are_corrected_only_when_nothing_matches(self):
        results, corrected = search(CATALOG, "hodie")
        self.assertEqual((names(results), corrected), (["Everyday Hoodie"], "hoodie"))
        results, corrected = search(CATALOG, "ceramik mugg")
        self.assertEqual((names(results), corrected), (["Ceramic Mug"], "ceramic mug"))
        self.assertEqual(search(CATALOG, "hodie", allow_correction=False), ([], None))
        self.assertEqual(search(CATALOG, "zzzzqq"), ([], None))

    def test_correction_leaves_good_words_alone(self):
        self.assertIsNone(correct(["mug"], {"mug", "ceramic"}))
        self.assertEqual(correct(["ceramic", "mugg"], {"mug", "ceramic"}), ["ceramic", "mug"])


class SearchPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        home = Category.objects.create(name="Home")
        Product.objects.create(name="Ceramic Mug", price=Decimal("14.50"), stock=5, category=home,
                               description="Stoneware mug.")
        Product.objects.create(name="Soy Candle", price=Decimal("18.00"), stock=5, category=home,
                               description="Pairs well with a mug of tea.")
        Product.objects.create(name="Steel Water Bottle", price=Decimal("29.00"), stock=5)

    def get(self, **params):
        return self.client.get(reverse("products:list"), params)

    def test_results_are_ranked(self):
        response = self.get(q="mug")
        self.assertEqual([p.name for p in response.context["products"]], ["Ceramic Mug", "Soy Candle"])
        self.assertContains(response, "Results for “mug”")

    def test_typo_shows_correction_with_exact_search_link(self):
        response = self.get(q="ceramik")
        self.assertEqual([p.name for p in response.context["products"]], ["Ceramic Mug"])
        self.assertContains(response, "showing results for <strong>ceramic</strong>")
        self.assertContains(response, "?q=ceramik&amp;exact=1")
        exact = self.get(q="ceramik", exact="1")
        self.assertEqual(exact.context["products"], [])
        self.assertContains(exact, "No products found")

    def test_search_within_a_category_keeps_both(self):
        response = self.get(q="mug", category="home")
        self.assertContains(response, "2 items in Home")
        self.assertContains(response, 'href="/?category=home&amp;q=mug"')
