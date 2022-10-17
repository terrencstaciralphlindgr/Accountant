from django.urls import path, include
from rest_framework import routers
from account.api.views import AccountViewSet, BalanceViewSet
from account.api.widgets.summary.views import *


router = routers.DefaultRouter()
router.register('accounts', AccountViewSet, basename="accounts-list")
router.register('balance', BalanceViewSet, basename="balances-list")

urlpatterns = [
    path('', include(router.urls)),
    path('account/<int:account_id>/summary/portfolio_value/', AssetValueViewSet.as_view()),
    path('account/<int:account_id>/summary/portfolio_growth/', AssetGrowthViewSet.as_view()),
    path('account/<int:account_id>/summary/portfolio_exposition/', ExpositionViewSet.as_view()),
    path('account/<int:account_id>/summary/portfolio_hist_value/', HistoricalValueViewSet.as_view()),
    path('account/<int:account_id>/summary/portfolio_hist_weight/', HistoricalWeightsViewSet.as_view()),
]
