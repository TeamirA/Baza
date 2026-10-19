import io
import os
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from config.media_store import LocalMediaStore, MediaStoreError, VercelBlobStore

from .images import ImageProcessingError, process_image
from .models import Product, ProductImage
from .services import ImageUploadError, ProductImageService, ProductService


def make_image(width, height, fmt="PNG", mode="RGB", exif_orientation=None):
    image = Image.new(mode, (width, height), (180, 90, 40) if mode == "RGB" else (180, 90, 40, 120))
    buffer = io.BytesIO()
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif
    image.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


class FakeStore:
    def __init__(self, fail_on=None):
        self.files = {}
        self.deleted = []
        self.fail_on = fail_on

    def save(self, path, data, content_type):
        if self.fail_on and self.fail_on in path:
            raise MediaStoreError("disk full")
        url = f"https://blob.example/{path}"
        self.files[url] = data
        return url

    def delete(self, urls):
        self.deleted.extend(urls)


class ProcessImageTests(SimpleTestCase):
    def test_large_photo_gets_three_webp_sizes(self):
        result = process_image(make_image(3000, 2000, "JPEG"))
        self.assertEqual(sorted(result.variants), [400, 800, 1600])
        self.assertEqual((result.width, result.height), (1600, 1067))
        for data in result.variants.values():
            self.assertEqual(Image.open(io.BytesIO(data)).format, "WEBP")

    def test_small_photo_is_never_upscaled(self):
        result = process_image(make_image(500, 500))
        self.assertEqual(sorted(result.variants), [400, 500])

    def test_transparency_is_kept(self):
        result = process_image(make_image(300, 300, mode="RGBA"))
        self.assertEqual(Image.open(io.BytesIO(result.variants[300])).mode, "RGBA")

    def test_phone_rotation_is_applied(self):
        # Orientation 6 = rotate 90°: a landscape sensor image displays as portrait.
        result = process_image(make_image(1200, 800, "JPEG", exif_orientation=6))
        self.assertGreater(result.height, result.width)

    def test_non_images_are_rejected(self):
        with self.assertRaises(ImageProcessingError):
            process_image(b"definitely not a picture")


class ProductImageServiceTests(TestCase):
    def setUp(self):
        self.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)

    def test_upload_saves_variants_and_records_photo(self):
        store = FakeStore()
        image = ProductImageService(store=store).add_image(self.mug.pk, make_image(2000, 1000), alt_text="Mug, side")
        self.assertEqual(sorted(image.variants, key=int), ["400", "800", "1600"])
        self.assertTrue(all(url.startswith("https://blob.example/products/mug/") for url in image.variants.values()))
        self.assertEqual(len(store.files), 3)
        self.assertEqual((image.width, image.height, image.alt_text, image.position), (1600, 800, "Mug, side", 0))
        second = ProductImageService(store=store).add_image(self.mug.pk, make_image(800, 800))
        self.assertEqual(second.position, 1)

    def test_failed_upload_removes_partial_files_and_saves_nothing(self):
        store = FakeStore(fail_on="-1600.webp")
        with self.assertRaises(ImageUploadError):
            ProductImageService(store=store).add_image(self.mug.pk, make_image(2000, 1000))
        self.assertFalse(ProductImage.objects.exists())
        self.assertEqual(sorted(store.deleted), sorted(store.files))  # 400 and 800 cleaned up

    @override_settings(MAX_IMAGE_UPLOAD_BYTES=1000)
    def test_oversized_upload_is_refused_with_a_clear_message(self):
        with self.assertRaisesMessage(ImageUploadError, "Photos must be under"):
            ProductImageService.prepare(b"x" * 2000)

    def test_deleting_a_photo_deletes_its_files_after_commit(self):
        image = ProductImageService(store=FakeStore()).add_image(self.mug.pk, make_image(900, 600))
        urls = sorted(image.variants.values())
        store = FakeStore()
        with mock.patch("products.signals.get_media_store", return_value=store):
            with self.captureOnCommitCallbacks(execute=True):
                self.mug.delete()  # cascades to the photo
        self.assertEqual(sorted(store.deleted), urls)


class ProductImageDTOTests(TestCase):
    def test_srcset_default_size_and_order(self):
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        ProductImage.objects.create(
            product=mug, position=1, width=1600, height=1600,
            variants={"1600": "https://b/m-1600.webp", "400": "https://b/m-400.webp", "800": "https://b/m-800.webp"},
        )
        ProductImage.objects.create(product=mug, position=0, width=400, height=400, variants={"400": "https://b/c-400.webp"})
        product = ProductService().get_product("mug")
        self.assertEqual([i.url for i in product.images], ["https://b/c-400.webp", "https://b/m-800.webp"])
        second = product.images[1]
        self.assertEqual(second.srcset, "https://b/m-400.webp 400w, https://b/m-800.webp 800w, https://b/m-1600.webp 1600w")
        self.assertEqual((second.thumb_url, second.large_url), ("https://b/m-400.webp", "https://b/m-1600.webp"))
        self.assertEqual(product.hover_image, second)

    def test_legacy_image_url_still_works(self):
        Product.objects.create(name="Old", price=Decimal("1.00"), image_url="https://cdn.example/old.jpg")
        product = ProductService().get_product("old")
        self.assertEqual(product.cover.url, "https://cdn.example/old.jpg")
        self.assertIsNone(product.hover_image)


class VercelBlobStoreTests(SimpleTestCase):
    def test_upload_request(self):
        session = mock.Mock()
        session.put.return_value = mock.Mock(status_code=200, json=lambda: {"url": "https://x.public.blob.vercel-storage.com/a.webp"})
        url = VercelBlobStore("tok", session=session).save("products/a.webp", b"data", "image/webp")
        self.assertEqual(url, "https://x.public.blob.vercel-storage.com/a.webp")
        args, kwargs = session.put.call_args
        self.assertEqual(args[0], "https://vercel.com/api/blob")
        self.assertEqual(kwargs["params"], {"pathname": "products/a.webp"})
        self.assertEqual(kwargs["headers"]["authorization"], "Bearer tok")
        self.assertEqual(kwargs["headers"]["x-api-version"], "11")
        self.assertEqual(kwargs["headers"]["x-content-type"], "image/webp")

    def test_auth_errors_explain_what_to_check(self):
        session = mock.Mock()
        session.put.return_value = mock.Mock(status_code=403, json=lambda: {"error": {"message": "Forbidden"}})
        with self.assertRaisesMessage(MediaStoreError, "Check BLOB_READ_WRITE_TOKEN and that the store is public"):
            VercelBlobStore("tok", session=session).save("a.webp", b"d", "image/webp")

    def test_delete_request(self):
        session = mock.Mock()
        session.post.return_value = mock.Mock(status_code=200)
        VercelBlobStore("tok", session=session).delete(["https://x/a.webp", ""])
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "https://vercel.com/api/blob/delete")
        self.assertEqual(kwargs["json"], {"urls": ["https://x/a.webp"]})


class LocalMediaStoreTests(SimpleTestCase):
    def test_save_and_delete(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        store = LocalMediaStore(root=root, base_url="/media/")
        url = store.save("products/a/b-400.webp", b"abc", "image/webp")
        self.assertEqual(url, "/media/products/a/b-400.webp")
        store.delete([url])
        self.assertFalse(os.path.exists(f"{root}/products/a/b-400.webp"))


class StorefrontImageTests(TestCase):
    def setUp(self):
        self.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        store = FakeStore()
        for size in [(1200, 1200), (1000, 1000)]:
            ProductImageService(store=store).add_image(self.mug.pk, make_image(*size))
        Product.objects.create(name="Bare", price=Decimal("1.00"), stock=5)

    def test_cards_use_responsive_cover_and_hover_photo(self):
        html = self.client.get(reverse("products:list")).content.decode()
        self.assertIn('srcset="https://blob.example/products/mug/', html)
        self.assertEqual(html.count('class="product-card__img product-card__img--hover"'), 1)  # only Mug has 2 photos
        self.assertIn("product-card__placeholder", html)  # "Bare" has no photos

    def test_product_page_gallery(self):
        html = self.client.get(self.mug.get_absolute_url()).content.decode()
        self.assertEqual(html.count('class="gallery__slide"'), 2)
        self.assertEqual(html.count('class="gallery__thumb"'), 2)
        self.assertIn('fetchpriority="high"', html)
        self.assertIn("gallery__zoom", html)
        bare = self.client.get(reverse("products:detail", args=["bare"])).content.decode()
        self.assertIn("gallery--empty", bare)
        self.assertNotIn('class="gallery__thumb"', bare)


class AdminPhotoUploadTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media)
        self.mug = Product.objects.create(name="Mug", slug="mug", price=Decimal("10.00"), stock=5)
        self.client.force_login(User.objects.create_superuser("boss", "boss@example.com", "x-Strong-pass-12"))

    def post(self, upload, alt="Front"):
        data = {
            "name": "Mug", "slug": "mug", "description": "", "price": "10.00", "image_url": "", "stock": "5",
            "is_active": "on", "category": "",
            "images-TOTAL_FORMS": "1", "images-INITIAL_FORMS": "0", "images-MIN_NUM_FORMS": "0", "images-MAX_NUM_FORMS": "1000",
            "images-0-upload": upload, "images-0-alt_text": alt, "images-0-position": "0", "images-0-product": self.mug.pk,
        }
        with override_settings(MEDIA_ROOT=self.media, BLOB_READ_WRITE_TOKEN=""):
            return self.client.post(reverse("admin:products_product_change", args=[self.mug.pk]), data)

    def test_uploading_a_photo_in_the_admin(self):
        response = self.post(SimpleUploadedFile("mug.jpg", make_image(1000, 800, "JPEG"), content_type="image/jpeg"))
        self.assertEqual(response.status_code, 302)
        image = self.mug.images.get()
        self.assertEqual(image.alt_text, "Front")
        self.assertEqual(sorted(image.variants, key=int), ["400", "800", "1000"])
        self.assertTrue(image.variants["400"].startswith("/media/products/mug/"))

    def test_bad_file_shows_an_error_on_the_form(self):
        response = self.post(SimpleUploadedFile("notes.jpg", b"not an image", content_type="image/jpeg"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.mug.images.exists())
        self.assertContains(response, "Upload a valid image")


class SeedPhotosTests(TestCase):
    def test_sample_products_get_two_photos_once(self):
        from django.core.management import call_command

        call_command("seed_products", verbosity=0, stdout=io.StringIO())
        store = FakeStore()
        with mock.patch("products.services.get_media_store", return_value=store):
            call_command("seed_products", photos_only=True, stdout=io.StringIO())
            call_command("seed_products", photos_only=True, stdout=io.StringIO())  # idempotent
        mug = Product.objects.get(slug="ceramic-mug")
        self.assertEqual(list(mug.images.values_list("alt_text", flat=True)), ["Ceramic Mug, front view", "Ceramic Mug, close-up"])
        self.assertEqual(ProductImage.objects.count(), 9 * 2)
        self.assertEqual(len(store.files), 9 * 2 * 3)  # 3 sizes per photo

    def test_products_with_photos_or_unknown_slugs_are_left_alone(self):
        from django.core.management import call_command

        own = Product.objects.create(name="Mine", price=Decimal("1.00"))
        with mock.patch("products.services.get_media_store", return_value=FakeStore()):
            call_command("seed_products", photos_only=True, stdout=io.StringIO())
        self.assertFalse(own.images.exists())
