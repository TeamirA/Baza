import logging
from dataclasses import replace

from django.core.paginator import Paginator
from django.shortcuts import render

from .dtos import BrowseFilters
from .forms import BrowseForm
from .services import ProductNotFound, ProductService

logger = logging.getLogger(__name__)


PAGE_SIZE = 12


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
