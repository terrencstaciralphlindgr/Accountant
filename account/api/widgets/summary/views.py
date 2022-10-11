from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import ValidationError
from account.models import Balance, Account
import structlog

log = structlog.get_logger(__name__)


@permission_classes([IsAdminUser])
class AssetValueViewSet(APIView):

    def get(self, request, account_id):

        period = request.GET.get('period')
        log.info('Return asset value', period=period)

        dic = Balance.objects.filter(account__id=account_id).latest('dt').calculate_assets_value()

        return Response(dict(
            total_value=dic['assets_total_value'],
            last_update=dic['last_update'],
            )
        )


@permission_classes([IsAdminUser])
class AssetGrowthViewSet(APIView):

    def get(self, request, account_id):

        period = request.GET.get('period')
        log.info('Return growth', period=period)

        growth = Account.objects.get(id=account_id).growth(period)
        return Response(growth)

