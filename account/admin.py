from django.contrib import admin
from account.models import Account, Order, Trade, Balance
from account.tasks import fetch_orders, fetch_trades
from pnl.tasks import update_asset_inventory, update_contract_inventory
from django.db.models import JSONField
from prettyjson import PrettyJSONWidget

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Account)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'exchange', 'quote',)
    readonly_fields = ('pk', 'name', 'exchange', 'quote',)
    ordering = ('pk',)
    actions = ['fetch_orders', 'fetch_trades', 'asset_inventory', 'contract_inventory']

    def fetch_orders(self, request, queryset):
        for obj in queryset:
            fetch_orders.delay(obj.pk)

    fetch_orders.short_description = 'Fetch orders'

    def fetch_trades(self, request, queryset):
        for obj in queryset:
            fetch_trades.delay(obj.pk)

    fetch_trades.short_description = 'Fetch trades'

    def asset_inventory(self, request, queryset):
        for obj in queryset:
            update_asset_inventory.delay(obj.pk)

    asset_inventory.short_description = 'Update inventory of assets'

    def contract_inventory(self, request, queryset):
        for obj in queryset:
            update_contract_inventory.delay(obj.pk)

    contract_inventory.short_description = 'Update inventory of contracts'


@admin.register(Order)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('orderid', 'account', 'market', 'clientid', 'status', 'type', 'amount', 'remaining', 'filled',
                    'side', 'cost', 'average', 'price', 'datetime')
    readonly_fields = ('orderid', 'account', 'market', 'clientid', 'status', 'type', 'amount', 'remaining', 'filled',
                       'side', 'cost', 'average', 'price', 'datetime', 'dt_created', )
    ordering = ('-datetime',)
    list_filter = (
        ('account', admin.RelatedOnlyFieldListFilter),
        ('market', admin.RelatedOnlyFieldListFilter)
    )


@admin.register(Trade)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('tradeid', 'account', 'order', 'symbol', 'side', 'type', 'taker_or_maker', 'datetime',)
    readonly_fields = ('tradeid', 'id', 'account', 'order', 'symbol', 'side', 'type', 'taker_or_maker', 'price',
                       'amount', 'cost', 'datetime', 'timestamp', 'fee', 'fees', 'info', 'dt_created', )
    ordering = ('-datetime',)
    list_filter = (
        ('account', admin.RelatedOnlyFieldListFilter),
        'symbol', 'side', 'taker_or_maker', 'type',
    )


@admin.register(Balance)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('dt', 'account', 'assets_total_value',)
    readonly_fields = ('assets_total_value', 'dt', 'account',)
    ordering = ('-dt',)

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }