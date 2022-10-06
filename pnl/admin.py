from django.contrib import admin
from pnl.models import Inventory

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Inventory)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('trade', 'get_side', 'get_amount', 'account', 'exchange', 'currency', 'instrument', 'get_stock',
                    'get_total_cost',
                    'average_cost', 'get_realized_pnl', 'get_unrealized_pnl', 'datetime')
    readonly_fields = ('trade', 'id', 'account', 'exchange', 'currency', 'instrument', 'stock', 'total_cost',
                       'average_cost', 'realized_pnl', 'unrealized_pnl', 'datetime')
    ordering = ('-datetime',)
    actions = ['', ]
    list_filter = (
        ('account', admin.RelatedOnlyFieldListFilter),
        ('exchange', admin.RelatedOnlyFieldListFilter),
        'instrument',
    )

    def get_side(self, obj):
        return obj.trade.side

    get_side.short_description = 'Side'

    def get_amount(self, obj):
        return obj.trade.amount

    get_amount.short_description = 'Amount'

    def get_realized_pnl(self, obj):
        if obj.realized_pnl:
            return round(obj.realized_pnl, 2)

    get_realized_pnl.short_description = 'Realized PnL'

    def get_unrealized_pnl(self, obj):
        if obj.unrealized_pnl:
            return round(obj.unrealized_pnl, 2)

    get_unrealized_pnl.short_description = 'Unrealized PnL'

    def get_stock(self, obj):
        if obj.stock:
            return round(obj.stock, 4)

    get_stock.short_description = 'Stock'

    def get_total_cost(self, obj):
        if obj.total_cost:
            return round(obj.total_cost, 2)

    get_total_cost.short_description = 'Total cost'
