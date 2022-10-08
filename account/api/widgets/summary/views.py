from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from account.models import Balance
import structlog

log = structlog.get_logger(__name__)


@permission_classes([IsAdminUser])
class AssetValueViewSet(APIView):
    def get(self, request, account_id):
        asset_value = Balance.objects.filter(account__id=account_id).latest('dt')
        Response(dict(asset_value=asset_value, growth=0))
