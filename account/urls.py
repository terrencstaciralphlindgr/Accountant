from django.urls import path, include
from rest_framework import routers
from account.api.views import AccountViewSet, BalanceViewSet
from account.api.widgets.summary.views import *


router = routers.DefaultRouter()
router.register('accounts', AccountViewSet, basename="accounts-list")
router.register('balance', BalanceViewSet, basename="balances-list")

urlpatterns = [
    path('', include(router.urls)),
    path('account/<int:account_id>/summary/assets/', AssetsViewSet.as_view()),
    path('account/<int:account_id>/summary/assets_value/', AssetsValueViewSet.as_view()),
    path('account/<int:account_id>/summary/assets_growth/', AssetsGrowthViewSet.as_view()),
    path('account/<int:account_id>/summary/assets_exposition/', AssetsExpositionViewSet.as_view()),
    path('account/<int:account_id>/summary/historical_value/', HistoricalValueViewSet.as_view()),
    path('account/<int:account_id>/summary/historical_weight/', HistoricalWeightsViewSet.as_view()),
    path('account/<int:account_id>/summary/historical_trades/', HistoricalTradesViewSet.as_view()),
]
