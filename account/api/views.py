from rest_framework import viewsets, mixins
from account.models import Account
from account.api.serializers import AccountSerializer
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser


# Create operation
@permission_classes([IsAdminUser])
class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    http_method_names = ['post']
