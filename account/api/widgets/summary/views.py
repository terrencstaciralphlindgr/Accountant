from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from account.models import Balance
import structlog

log = structlog.get_logger(__name__)


class AssetValueViewSet(APIView):
    """
    Returns True if an order ID is valid else False.
    * Only admin users are able to access this view.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, account_id):
        asset_value = Balance.objects.filter(account__id=account_id).latest('dt').assets_total_value
        Response(dict(asset_value=asset_value, growth=0))
