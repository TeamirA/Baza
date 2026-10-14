import logging

from django.shortcuts import render

from .services import ProductNotFound, ProductService

logger = logging.getLogger(__name__)


def product_list(request):
    category_slug = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()
    context = {"products": [], "categories": [], "active_category": None, "query": query}
    try:
        service = ProductService()
        context["categories"] = service.list_categories()
        if category_slug:
            context["active_category"] = service.get_category(category_slug)
            if context["active_category"] is None:
                context["error"] = f'There is no category called "{category_slug}". Showing all products.'
                category_slug = ""
        context["products"] = service.list_products(category_slug or None, query or None)
    except Exception as e:
        logger.exception("Failed to load product list")
        context["error"] = f"We couldn't load products right now: {e}"
    return render(request, "products/product_list.html", context)


def product_detail(request, slug):
    try:
        product = ProductService().get_product(slug)
    except ProductNotFound as e:
        return render(request, "products/product_detail.html", {"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Failed to load product %s", slug)
        return render(
            request, "products/product_detail.html", {"error": f"We couldn't load this product: {e}"}, status=500
        )
    return render(request, "products/product_detail.html", {"product": product})
