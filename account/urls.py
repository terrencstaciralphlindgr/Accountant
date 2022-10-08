from django.urls import path, include
from rest_framework import routers
from account.api.views import AccountViewSet, BalanceViewSet


router = routers.DefaultRouter()
router.register('account', AccountViewSet, basename="accounts-list")
router.register('balance', BalanceViewSet, basename="balances-list")

urlpatterns = [
    path('', include(router.urls)),
]