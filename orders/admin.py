from django.contrib import admin, messages

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "price"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "status", "total", "amount_paid", "created_at"]
    list_filter = ["status", "created_at"]
    list_editable = ["status"]
    search_fields = ["id", "user__username", "email", "stripe_session_id"]
    inlines = [OrderItemInline]
    actions = ["cancel_unpaid_orders"]

    def save_model(self, request, obj, form, change):
        just_shipped = change and "status" in form.changed_data and obj.status == Order.Status.SHIPPED
        super().save_model(request, obj, form, change)
        if just_shipped:
            from orders.notifications import send_order_email
            from orders.services import OrderService

            if send_order_email(OrderService().get_order(obj.pk), "shipped"):
                self.message_user(request, f"Emailed {obj.email} that order #{obj.pk} has shipped.", messages.INFO)

    @admin.action(description="Cancel selected unpaid orders (puts stock back)")
    def cancel_unpaid_orders(self, request, queryset):
        from orders.services import OrderService
        from payments.services import PaymentService

        cancelled = 0
        for order_id in queryset.filter(status=Order.Status.PENDING).values_list("pk", flat=True):
            _, was_cancelled = PaymentService().cancel_order(OrderService().get_order(order_id))
            cancelled += was_cancelled
        self.message_user(request, f"Cancelled {cancelled} order(s).", messages.SUCCESS)
