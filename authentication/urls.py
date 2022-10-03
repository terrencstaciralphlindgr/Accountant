from django.urls import path, include
from rest_framework import routers
from authentication.api.views import UsersView


router = routers.DefaultRouter()
router.register("users", UsersView, basename="users-list")

urlpatterns = [
    path("api/", include(router.urls)),
]
