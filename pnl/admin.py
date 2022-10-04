from django.contrib import admin
from pnl.models import Inventory, AssetPnl

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Inventory)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', )
    readonly_fields = ('id', )
    ordering = ('pk',)
    actions = ['', ]
