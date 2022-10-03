from django.contrib import admin
from authentication.models import User

admin.autodiscover()
admin.site.enable_nav_sidebar = False


@admin.register(User)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'password', 'dt_created', 'dt_modified',)
    readonly_fields = ('token', 'password', 'last_login', 'dt_created', 'dt_modified',)
    actions = []
    save_as = True
    save_on_top = True

