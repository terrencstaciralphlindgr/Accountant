from django.contrib import admin
from pnl.models import Inventory

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Inventory)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('trade', 'account', 'exchange', 'currency', 'instrument', 'stock', 'total_cost', 'average_cost',
                    'realized_pnl', 'unrealized_pnl', 'datetime')
    readonly_fields = ('trade', 'id', 'account', 'exchange', 'currency', 'instrument', 'stock', 'total_cost',
                       'average_cost', 'realized_pnl', 'unrealized_pnl', 'datetime')
    ordering = ('-datetime',)
    actions = ['', ]
