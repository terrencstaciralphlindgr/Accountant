from django.urls import path, include
from rest_framework import routers
from account.api.views import AccountViewSet, BalanceViewSet
from account.api.widgets.summary.views import AssetValueViewSet


router = routers.DefaultRouter()
router.register('accounts', AccountViewSet, basename="accounts-list")
router.register('balance', BalanceViewSet, basename="balances-list")

urlpatterns = [
    path('', include(router.urls)),
    path('widget/summary/asset_value/<int:account_id>/', AssetValueViewSet.as_view(), name='asset_value'),
]