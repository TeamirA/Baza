import logging
from dataclasses import replace

from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from .dtos import BrowseFilters
from .forms import BrowseForm, ReviewForm
from .recently_viewed import RecentlyViewedStore
from .services import ProductNotFound, ProductService, ReviewNotAllowed, ReviewService, WishlistService

logger = logging.getLogger(__name__)


PAGE_SIZE = 12
ROW_SIZE = 4


def recently_viewed(request, service, exclude_id=None):
    """Recently viewed products for this browser; never breaks the page."""
    try:
        return service.products_in_order(RecentlyViewedStore(request.session).ids(), exclude_id, ROW_SIZE)
    except Exception:
        logger.exception("Failed to load recently viewed products")
        return []


def product_list(request):
    form = BrowseForm(request.GET)
    form.is_valid()  # invalid fields are simply left out of cleaned_data
    data = form.cleaned_data
    filters = BrowseFilters(
        query=data.get("q", ""),
        category_slug=data.get("category", ""),
        min_price=data.get("min_price"),
        max_price=data.get("max_price"),
        in_stock=data.get("in_stock", False),
        sort=data.get("sort", ""),
        exact=data.get("exact", False),
    )
    context = {
        "form": form,
        "filters": filters,
        "query": filters.query,
        "products": [],
        "categories": [],
        "active_category": None,
        "corrected_query": None,
    }
    errors = [f"{form.fields[name].label or name}: {' '.join(msgs)}" for name, msgs in form.errors.items()]
    if errors:
        context["error"] = "Some filters were ignored. " + " ".join(errors)

    try:
        service = ProductService()
        context["categories"] = service.list_categories()
        if filters.category_slug:
            context["active_category"] = service.get_category(filters.category_slug)
            if context["active_category"] is None:
                context["error"] = f'There is no category called "{filters.category_slug}". Showing all products.'
                filters = replace(filters, category_slug="")
        products, context["corrected_query"], context["sort"] = service.browse(filters)
    except Exception as e:
        logger.exception("Failed to load product list")
        context["error"] = f"We couldn't load products right now: {e}"
        return render(request, "products/product_list.html", context)

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    browsing_home = not (filters.query or filters.category_slug or filters.is_filtered) and page.number == 1
    context["recently_viewed"] = recently_viewed(request, service) if browsing_home else []
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("category", None)
    chip_query = params.urlencode()  # what category chips keep when switching category
    params = request.GET.copy()
    params.pop("page", None)
    context.update(
        products=page.object_list,
        page_obj=page,
        total=page.paginator.count,
        querystring=params.urlencode(),
        chip_query=chip_query,
    )
    return render(request, "products/product_list.html", context)


def product_detail(request, slug, review_form=None):
    service = ProductService()
    try:
        product = service.get_product(slug)
    except ProductNotFound:
        return render(request, "products/product_detail.html", {"query_hint": slug.replace("-", " ")}, status=404)
    except Exception as e:
        logger.exception("Failed to load product %s", slug)
        return render(
            request, "products/product_detail.html", {"error": f"We couldn't load this product: {e}"}, status=500
        )
    viewed_before = recently_viewed(request, service, exclude_id=product.id)
    review_context = _review_context(request, product, review_form)
    RecentlyViewedStore(request.session).add(product.id)
    try:
        related = service.related_products(product)
    except Exception:
        # Suggestions are a nice-to-have; never fail the product page over them.
        logger.exception("Failed to load related products for %s", slug)
        related = []
    related_same_category = bool(related) and product.category is not None and all(
        item.category == product.category for item in related
    )
    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "related": related,
            "related_same_category": related_same_category,
            "recently_viewed": viewed_before,
            **review_context,
        },
    )


SUGGEST_MIN_CHARS = 2


@require_GET
def search_suggest(request):
    """JSON for the header search box's live suggestions."""
    query = request.GET.get("q", "").strip()[:100]
    results, total, corrected = [], 0, None
    if len(query) >= SUGGEST_MIN_CHARS:
        try:
            products, total, corrected = ProductService().suggest(query)
            results = [
                {
                    "name": p.name,
                    "url": p.url,
                    "price": f"{p.price:,.2f}",
                    "category": p.category.name if p.category else "",
                    "image": p.cover.thumb_url if p.cover else "",
                    "in_stock": p.in_stock,
                }
                for p in products
            ]
        except Exception:
            logger.exception("Search suggestions failed for %r", query)
    response = JsonResponse({
        "query": query,
        "corrected": corrected,
        "total": total,
        "results": results,
        "see_all_url": f"{reverse('products:list')}?{urlencode({'q': query})}" if query else reverse("products:list"),
    })
    response["Cache-Control"] = "public, max-age=60"
    return response


def _review_context(request, product, form=None):
    """Reviews, and whether/how this shopper can write one. Never breaks the page."""
    reviews = ReviewService()
    try:
        own = reviews.own_review(request.user, product.id)
        can_review = reviews.can_review(request.user, product.id)
        if form is None and can_review:
            initial = {"rating": own.rating, "title": own.title, "body": own.body} if own else None
            form = ReviewForm(initial=initial)
        return {
            "reviews": reviews.list_for_product(product.id, request.user),
            "can_review": can_review,
            "has_own_review": own is not None,
            "review_form": form,
        }
    except Exception:
        logger.exception("Failed to load reviews for product %s", product.id)
        return {"reviews": [], "can_review": False, "has_own_review": False, "review_form": None}


@login_required
@require_POST
def review_submit(request, slug):
    try:
        product = ProductService().get_product(slug)
    except ProductNotFound as e:
        messages.error(request, str(e))
        return redirect("products:list")
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please fix the review form below.")
        return product_detail(request, slug, review_form=form)
    try:
        ReviewService().save(request.user, product.id, **form.cleaned_data)
    except ReviewNotAllowed as e:
        messages.error(request, str(e))
        return redirect(product.url)
    messages.success(request, "Thanks! Your review is posted.")
    return redirect(f"{product.url}#reviews")


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@login_required
@require_POST
def wishlist_toggle(request, product_id):
    service = WishlistService(request.user)
    try:
        saved = service.toggle(product_id)
    except ProductNotFound as e:
        if _wants_json(request):
            return JsonResponse({"error": str(e)}, status=404)
        messages.error(request, str(e))
        return redirect("products:wishlist")
    if _wants_json(request):
        return JsonResponse({"saved": saved, "count": len(service.ids())})
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("products:wishlist")


@login_required
def wishlist(request):
    try:
        items = WishlistService(request.user).items()
    except Exception as e:
        logger.exception("Failed to load wishlist")
        return render(request, "products/wishlist.html", {"items": [], "error": f"We couldn't load your saved items: {e}"})
    return render(request, "products/wishlist.html", {"items": items})


@login_required
@require_POST
def wishlist_move_to_cart(request, product_id):
    """Adds a saved product to the cart and takes it off the wishlist."""
    from orders.services import CartError, CartService

    try:
        product = CartService.for_request(request).add(product_id, 1)
    except CartError as e:
        messages.error(request, str(e))
        return redirect("products:wishlist")
    WishlistService(request.user).remove(product_id)
    messages.success(request, f"Moved {product.name} to your cart.")
    return redirect("products:wishlist")
