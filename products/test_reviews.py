from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem

from .models import Product, Review

PASSWORD = "a-Strong-test-pass-91"


class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        cls.buyer = User.objects.create_user("sam", "sam@example.com", PASSWORD, first_name="Sam", last_name="Doe")
        cls.browser = User.objects.create_user("alex", "alex@example.com", PASSWORD)
        cls.pending_buyer = User.objects.create_user("kim", "kim@example.com", PASSWORD)
        for user, status in [(cls.buyer, Order.Status.PAID), (cls.pending_buyer, Order.Status.PENDING)]:
            order = Order.objects.create(user=user, status=status)
            OrderItem.objects.create(order=order, product=cls.mug, quantity=1, price=cls.mug.price)

    def post(self, **data):
        return self.client.post(reverse("products:review", args=["mug"]), data, follow=True)

    def test_only_paid_buyers_see_the_form_and_can_post(self):
        self.assertContains(self.client.get("/products/mug/"), "Log in</a> to review")
        for user in (self.browser, self.pending_buyer):
            self.client.force_login(user)
            self.assertContains(self.client.get("/products/mug/"), "Only customers who bought this product")
            self.assertContains(self.post(rating="5"), "Only customers who bought this product can review it.")
        self.assertFalse(Review.objects.exists())

        self.client.force_login(self.buyer)
        self.assertContains(self.client.get("/products/mug/"), "Write a review")
        response = self.post(rating="4", title="Solid mug", body="Keeps coffee warm.")
        self.assertContains(response, "Thanks! Your review is posted.")
        self.assertContains(response, "Sam D. (you) · Verified purchase")
        self.assertContains(response, "Solid mug")

    def test_posting_again_edits_your_review(self):
        self.client.force_login(self.buyer)
        self.post(rating="2", title="Meh")
        page = self.client.get("/products/mug/")
        self.assertContains(page, "Edit your review")
        self.assertContains(page, 'value="2" checked')
        self.post(rating="5", title="Grew on me")
        review = Review.objects.get()
        self.assertEqual((review.rating, review.title), (5, "Grew on me"))

    def test_missing_or_bad_rating_shows_form_errors(self):
        self.client.force_login(self.buyer)
        response = self.post(rating="9", title="x")
        self.assertContains(response, "Please fix the review form below.")
        self.assertContains(response, "star-input--invalid")
        self.assertFalse(Review.objects.exists())

    def test_average_and_count_on_cards_and_page(self):
        other = User.objects.create_user("lee", "lee@example.com", PASSWORD)
        Review.objects.create(product=self.mug, user=self.buyer, rating=5)
        Review.objects.create(product=self.mug, user=other, rating=4)
        listing = self.client.get(reverse("products:list"))
        self.assertEqual((listing.context["products"][0].rating_avg, listing.context["products"][0].rating_count), (4.5, 2))
        self.assertContains(listing, 'aria-label="Rated 4.5 out of 5, 2 reviews"')
        page = self.client.get("/products/mug/")
        self.assertContains(page, "<strong>4.5</strong> out of 5 · 2 reviews")
        self.assertContains(page, "width: 90%")

    def test_products_without_reviews_show_no_stars(self):
        listing = self.client.get(reverse("products:list"))
        self.assertNotContains(listing, 'class="stars')
        self.assertContains(self.client.get("/products/mug/"), "No reviews yet.")

    def test_reviews_are_listed_in_admin(self):
        Review.objects.create(product=self.mug, user=self.buyer, rating=3, title="Okay")
        self.client.force_login(User.objects.create_superuser("boss", "boss@example.com", PASSWORD))
        self.assertContains(self.client.get(reverse("admin:products_review_changelist")), "Okay")
