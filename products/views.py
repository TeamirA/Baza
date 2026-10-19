import logging

from django.shortcuts import render

from .services import ProductNotFound, ProductService

logger = logging.getLogger(__name__)


def product_list(request):
    category_slug = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()[:100]
    exact = request.GET.get("exact") == "1"
    context = {"products": [], "categories": [], "active_category": None, "query": query, "corrected_query": None}
    try:
        service = ProductService()
        context["categories"] = service.list_categories()
        if category_slug:
            context["active_category"] = service.get_category(category_slug)
            if context["active_category"] is None:
                context["error"] = f'There is no category called "{category_slug}". Showing all products.'
                category_slug = ""
        if query:
            context["products"], context["corrected_query"] = service.search_products(
                query, category_slug or None, allow_correction=not exact
            )
        else:
            context["products"] = service.list_products(category_slug or None)
    except Exception as e:
        logger.exception("Failed to load product list")
        context["error"] = f"We couldn't load products right now: {e}"
    return render(request, "products/product_list.html", context)


def product_detail(request, slug):
    service = ProductService()
    try:
        product = service.get_product(slug)
    except ProductNotFound as e:
        return render(request, "products/product_detail.html", {"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Failed to load product %s", slug)
        return render(
            request, "products/product_detail.html", {"error": f"We couldn't load this product: {e}"}, status=500
        )
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
        {"product": product, "related": related, "related_same_category": related_same_category},
    )
