from django.contrib import admin
from market.models import Exchange, Market, Currency

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Exchange)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'exid', 'rounding_mode_spot', 'rounding_mode_future', 'padding_mode', 'dt_created',
                    'dt_modified',)
    readonly_fields = ('dt_created', 'dt_modified',)
    actions = []
    save_as = True
    save_on_top = True


@admin.register(Market)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'instrument', 'exchange', 'wallet', 'type', 'base', 'quote', 'margined',
                    'active', 'dt_modified',)
    readonly_fields = ('symbol', 'instrument', 'exchange', 'wallet', 'type', 'base', 'quote', 'margined',
                       'active', 'margin', 'contract_size', 'maker', 'taker', 'ticker', 'limits', 'precision', 'info',
                       'dt_created', 'dt_modified',)
    list_filter = ('exchange', 'type', 'active', 'wallet',
                   ('margined', admin.RelatedOnlyFieldListFilter),
                   ('quote', admin.RelatedOnlyFieldListFilter),
                   ('base', admin.RelatedOnlyFieldListFilter)
                   )
    actions = []
    ordering = ('base', 'type',)


@admin.register(Currency)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'dt_created', 'dt_modified',)
    readonly_fields = ('code', 'exchange', 'response', 'dt_created', 'dt_modified',)
    actions = []
    list_filter = (
        ('exchange', admin.RelatedOnlyFieldListFilter),
    )
    ordering = ('code',)
