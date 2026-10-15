import logging

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .dtos import RegistrationDTO
from .forms import RegistrationForm
from .services import UserService

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
