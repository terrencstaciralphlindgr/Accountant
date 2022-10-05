from django.contrib import admin
from pnl.models import Inventory

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Inventory)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('trade', 'get_side', 'account', 'exchange', 'currency', 'instrument', 'stock', 'total_cost',
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

    def get_realized_pnl(self, obj):
        if obj.realized_pnl:
            return obj.realized_pnl

    get_realized_pnl.short_description = 'Realized PnL'

    def get_unrealized_pnl(self, obj):
        if obj.unrealized_pnl:
            return obj.unrealized_pnl

    get_unrealized_pnl.short_description = 'Unrealized PnL'
