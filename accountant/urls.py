from django.contrib import admin
from django.urls import path, include
from authentication.api.views import SignUpView, LogInView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("account.urls")),

    path("auth/", include("authentication.urls")),
    path('users/api/sign_up/', SignUpView.as_view(), name='sign_up'),
    path('users/api/log_in/', LogInView.as_view(), name='log_in'),
]

admin.site.site_header = 'Quantly Accountant'
admin.site.site_title = 'Quantly Accountant'
