from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from accountant.methods import get_start_datetime
from account.models import Balance, Account
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

        price = Price.objects.filter(dt__gte=get_start_datetime(account, period)).order_by('-dt')
        price = price.values('last', 'dt')

        qs = Balance.objects.filter(account=account, dt__gte=get_start_datetime(account, period)).order_by('-dt')
        qs = qs.values('assets_total_value', 'dt')

        data = {}
        for (a, b) in zip(qs, price):
            str_date = a['dt'].strftime("%Y/%m/%d")
            if a['dt'] == b['dt']:
                data[str_date] = {}
                data[str_date]['last'] = b['last']
                data[str_date]['assets_total_value'] = a['assets_total_value']

        print(data)
        return Response(data)
