from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from account.models import Balance, Account
import structlog

log = structlog.get_logger(__name__)


@permission_classes([IsAdminUser])
class AssetValueViewSet(APIView):

    def get(self, request, account_id):

        period = request.GET.get('period')
        if period:

            log.info('Return asset value', period=period)

            asset_value = Balance.objects.filter(account__id=account_id).latest('dt').assets_total_value
            growth = Account.objects.get(id=account_id).growth(period)
            return Response(dict(asset_value=asset_value, growth=growth))

        else:
            log.error('Parameter str:period is required')
