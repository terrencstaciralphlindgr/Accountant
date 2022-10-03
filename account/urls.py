from django.urls import path, include
from rest_framework import routers
from account.api.views import AccountViewSet


router = routers.DefaultRouter()
router.register("", AccountViewSet, basename="accounts-list")

urlpatterns = [
    path('', include(router.urls)),
]