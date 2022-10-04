from django.contrib import admin
from account.models import Account, Order, Trade
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
            fetch_orders.delay(obj.pk)

    fetch_orders.short_description = 'Async Fetch Orders'

    def fetch_trades(self, request, queryset):
        for obj in queryset:
            fetch_trades.delay(obj.pk)

    fetch_trades.short_description = 'Async Fetch Trades'


@admin.register(Order)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('pk', 'account', 'market', 'clientid', )
    readonly_fields = ('pk', 'account', 'market', 'clientid', )
    ordering = ('pk',)


@admin.register(Trade)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('pk', 'account', 'order', 'tradeid', )
    readonly_fields = ('pk', 'account', 'order', 'tradeid', )
    ordering = ('pk',)
