from django.contrib import admin
from account.models import Account
from account.tasks import fetch_orders, fetch_trades

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Account)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'exchange', 'quote', )
    readonly_fields = ('pk', 'name', 'exchange', 'quote', )
    ordering = ('pk',)
    actions = ['fetch_orders', 'fetch_trades', ]

    def fetch_orders(self, request, queryset):
        for obj in queryset:
            fetch_trades.delay(obj.pk)

    fetch_orders.short_description = 'Async Fetch Orders'

    def fetch_trades(self, request, queryset):
        for obj in queryset:
            fetch_trades.delay(obj.pk)

    fetch_trades.short_description = 'Async Fetch Trades'
