from django.contrib import admin
from account.models import Account
from django.db.models import JSONField
from prettyjson import PrettyJSONWidget
from account.tasks import fetch_positions, fetch_account_balance

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(Account)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'exchange', 'quote', )
    readonly_fields = ('pk', 'name', 'exchange', 'quote', )
    ordering = ('pk',)
    actions = ['fetch_balance', 'fetch_position', ]

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }

    def fetch_balance(self, request, queryset):
        for obj in queryset:
            fetch_account_balance.delay(obj.pk)

    fetch_balance.short_description = 'Async Fetch Balance'

    def fetch_position(self, request, queryset):
        for obj in queryset:
            fetch_positions.delay(obj.pk)

    fetch_position.short_description = 'Async Fetch Position'
