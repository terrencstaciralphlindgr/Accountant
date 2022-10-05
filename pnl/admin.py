from django.contrib import admin
from pnl.models import Inventory

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Inventory)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('trade', 'get_side', 'account', 'exchange', 'currency', 'instrument', 'stock', 'total_cost',
                    'average_cost', 'realized_pnl', 'unrealized_pnl', 'datetime')
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
