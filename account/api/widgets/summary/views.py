from django.db.models.functions import Cast
from django.db.models import DateTimeField
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from accountant.methods import get_start_datetime, datetime_directive_ISO_8601
from account.models import Balance, Account, Trade
from market.models import Price
import structlog

log = structlog.get_logger(__name__)


@permission_classes([IsAdminUser])
class AssetValueViewSet(APIView):

    def get(self, request, account_id):
        dic = Balance.objects.filter(account__id=account_id).latest('dt').get_assets_value()
        return Response(dict(
            total_value=dic['assets_total_value'],
            last_update=dic['last_update'],
        )
        )


@permission_classes([IsAdminUser])
class AssetGrowthViewSet(APIView):

    def get(self, request, account_id):
        period = request.GET.get('period')
        growth = Account.objects.get(id=account_id).growth(period)
        return Response(growth)


@permission_classes([IsAdminUser])
class ExpositionViewSet(APIView):

    def get(self, request, account_id):
        exposition = Account.objects.get(id=account_id).current_exposition()
        return Response(exposition)


@permission_classes([IsAdminUser])
class HistoricalValueViewSet(APIView):

    def get(self, request, account_id):
        period = request.GET.get('period')
        account = Account.objects.get(id=account_id)
        start_datetime = get_start_datetime(account, period)

        price = Price.objects.filter(dt__gte=start_datetime, market__type='spot').annotate(
            date_only=Cast('dt', DateTimeField())).values("date_only", "last").order_by('-dt')

        qs = Balance.objects.filter(account=account, dt__gte=start_datetime).annotate(
            date_only=Cast('dt', DateTimeField())).values("date_only", "assets_total_value").order_by('-dt')

        data = {}
        for (a, b) in zip(qs, price):
            str_date = a['date_only'].strftime(datetime_directive_ISO_8601)
            if a['date_only'] == b['date_only']:
                data[str_date] = {}
                data[str_date]['bitcoin_price'] = b['last']
                data[str_date]['assets_total_value'] = a['assets_total_value']

        return Response(data)


@permission_classes([IsAdminUser])
class HistoricalWeightsViewSet(APIView):

    def get(self, request, account_id):
        period = request.GET.get('period')
        account = Account.objects.get(id=account_id)
        start_datetime = get_start_datetime(account, period)

        qs = Balance.objects.filter(account=account, dt__gte=start_datetime).annotate(
            date_only=Cast('dt', DateTimeField())).values("date_only", "assets").order_by('-dt')

        data = {}
        for a in qs:
            str_date = a['date_only'].strftime(datetime_directive_ISO_8601)
            data[str_date] = dict()
            codes = [c for c in a['assets'].keys() if c != 'last_update']
            for code in codes:
                if 'weight' in a['assets'][code]:
                    data[str_date][code] = dict()
                    data[str_date][code] = a['assets'][code]['weight']

        return Response(data)


@permission_classes([IsAdminUser])
class RecentTradesViewSet(APIView):

    def get(self, request, account_id):
        
        period = request.GET.get('period')
        last_n = request.GET.get('last_n')
        if not last_n:
            last_n = 5

        account = Account.objects.get(id=account_id)
        start_datetime = get_start_datetime(account, period)

        fields = ['tradeid', 'order__orderid',
                  'order__market__base__code',
                  'order__market__quote__code',
                  'order__market__type',
                  'order__market__exchange',
                  'symbol', 'side', 'taker_or_maker', 'price',
                  'amount', 'cost', 'fee', 'account', 'datetime', 'timestamp']

        qs = Trade.objects.filter(account=account, datetime__gte=start_datetime).annotate(
            date_only=Cast('datetime', DateTimeField())).order_by('-datetime').values(*fields)[:last_n]

        return Response(qs)
