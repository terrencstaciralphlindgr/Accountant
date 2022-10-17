from django.db.models.functions import Cast
from django.db.models import DateTimeField
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from accountant.methods import get_start_datetime, datetime_directive_ISO_8601
from account.models import Balance, Account, Trade
import structlog

log = structlog.get_logger(__name__)


@permission_classes([IsAdminUser])
class OpenPositionViewSet(APIView):

    def get(self, request, account_id):

        account = Account.objects.get(id=account_id)
        data = Balance.objects.filter(account=account).latest('-dt').values("open_position")

        return Response(data)


@permission_classes([IsAdminUser])
class NotionalValueViewSet(APIView):

    def get(self, request, account_id):

        account = Account.objects.get(id=account_id)
        data = Balance.objects.filter(account=account).latest('-dt').values("open_position")

        return Response(dict(notional_value=data['open_position']['notional_value']))


@permission_classes([IsAdminUser])
class ProfitAndLossViewSet(APIView):

    def get(self, request, account_id):
        period = request.GET.get('period')
        growth = Account.objects.get(id=account_id).growth(period)
        return Response(growth)


@permission_classes([IsAdminUser])
class MarginLevelViewSet(APIView):

    def get(self, request, account_id):
        exposition = Account.objects.get(id=account_id).current_exposition()
        return Response(exposition)


@permission_classes([IsAdminUser])
class RiskLevelViewSet(APIView):

    def get(self, request, account_id):

        period = request.GET.get('period')
        last_n = request.GET.get('last_n')
        if not last_n:
            last_n = 5

        account = Account.objects.get(id=account_id)
        start_datetime = get_start_datetime(account, period)

        fields = ['account', 'amount', 'cost', 'datetime', 'fee',
                  'order__orderid',
                  'order__market__base__code',
                  'order__market__quote__code',
                  'order__market__type',
                  'order__market__exchange',
                  'price', 'side', 'symbol', 'taker_or_maker', 'timestamp', 'tradeid']

        qs = Trade.objects.filter(account=account, datetime__gte=start_datetime).annotate(
            date_only=Cast('datetime', DateTimeField())).order_by('-datetime').values(*fields)[:int(last_n)]

        return Response(qs)
