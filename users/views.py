import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .dtos import RegistrationDTO
from .forms import AddressForm, EmailChangeForm, RegistrationForm
from .services import AddressError, AddressService, UserService

logger = logging.getLogger(__name__)


def register(request):
    if request.user.is_authenticated:
        return redirect("products:list")

    next_url = request.POST.get("next") or request.GET.get("next", "")
    form = RegistrationForm(request.POST or None)
    context = {"form": form, "next": next_url}

    if request.method == "POST" and form.is_valid():
        try:
            user = UserService().register(
                RegistrationDTO(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                )
            )
        except Exception as e:
            logger.exception("Registration failed")
            context["error"] = f"We couldn't create your account: {e}"
            return render(request, "users/register.html", context)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome, {user.username}! Your account is ready.")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("products:list")

    return render(request, "users/register.html", context)


def _profile_page(request, address_form=None, email_form=None, status=200):
    context = {
        "address_form": address_form or AddressForm(),
        "email_form": email_form or EmailChangeForm(request.user),
    }
    try:
        context["addresses"] = AddressService().list(request.user)
    except Exception as e:
        logger.exception("Failed to load addresses")
        context["addresses"] = []
        context["error"] = f"We couldn't load your saved addresses: {e}"
    return render(request, "users/profile.html", context, status=status)


@login_required
def profile(request):
    return _profile_page(request)


@login_required
@require_POST
def email_change(request):
    form = EmailChangeForm(request.user, request.POST)
    if not form.is_valid():
        return _profile_page(request, email_form=form, status=400)
    email = UserService().change_email(request.user, form.cleaned_data["email"])
    messages.success(request, f"Your email is now {email}.")
    return redirect("profile")


@login_required
@require_POST
def address_add(request):
    form = AddressForm(request.POST)
    if not form.is_valid():
        return _profile_page(request, address_form=form, status=400)
    try:
        AddressService().add(request.user, **form.cleaned_data)
    except AddressError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Address saved.")
    return redirect("profile")


@login_required
@require_POST
def address_default(request, address_id):
    try:
        AddressService().set_default(request.user, address_id)
    except AddressError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Default address updated.")
    return redirect("profile")


@login_required
@require_POST
def address_delete(request, address_id):
    try:
        AddressService().delete(request.user, address_id)
    except AddressError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Address deleted.")
    return redirect("profile")
