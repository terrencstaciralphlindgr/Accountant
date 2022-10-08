from rest_framework import viewsets
from account.api.serializers import AccountSerializer, BalanceSerializer
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser


# Create operation
@permission_classes([IsAdminUser])
class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    http_method_names = ['post']


@permission_classes([IsAdminUser])
class BalanceViewSet(viewsets.ModelViewSet):
    serializer_class = BalanceSerializer
    http_method_names = ['post']


@permission_classes([IsAdminUser])
class BalanceViewSet(viewsets.ModelViewSet):
    serializer_class = WidgetSummaryAssetValueSerializer
    http_method_names = ['get']
