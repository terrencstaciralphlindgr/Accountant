from pprint import pprint
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from account.models import Account, Balance
from market.models import Exchange, Currency
import structlog
log = structlog.get_logger(__name__)


class BalanceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Balance
        fields = ('id', 'dt', 'assets_total_value', 'assets', 'open_positions',)

    def create(self, validated_data):
        if self.is_valid():

            # Select account
            try:
                account = get_object_or_404(Account, id=validated_data['id'])
            except Exception as e:
                pprint(validated_data)
                log.error('Balance creation error', cause=str(e))
            else:
                try:
                    obj, created = Balance.objects.update_or_create(account=account,
                                                                    defaults=validated_data,
                                                                    dt=validated_data['dt']
                                                                    )
                except ValidationError:
                    pprint(validated_data)
                    log.error('Balance creation error')

                else:
                    log.info('Balance created')
                    return obj


class AccountSerializer(serializers.ModelSerializer):

    class Meta:
        model = Account
        fields = '__all__'

    def create(self, validated_data):
        if self.is_valid():

            pprint(validated_data)
            id = validated_data['response']['id']

            # Select Foreign Keys
            exid = validated_data['response']['foreign_keys']['exchange_exid']
            code_quote = validated_data['response']['foreign_keys']['code_quote']

            del validated_data['response']['foreign_keys']

            validated_data['exchange'] = get_object_or_404(Exchange, exid=exid)
            validated_data['quote'] = get_object_or_404(Currency, code=code_quote)

            try:
                obj, created = Account.objects.update_or_create(pk=id, defaults=validated_data)

            except ValidationError:
                pprint(validated_data)
                log.error('Account update_or_create failure')

            else:

                if created:
                    log.info('Account created')
                else:
                    log.info('Account updated')

                # print(created)
                # pprint(validated_data)
                # pprint(model_to_dict(obj))

                return obj
