from pprint import pprint
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from account.models import Account, Balance
from market.models import Exchange, Currency
import structlog
log = structlog.get_logger(__name__)


class BalanceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Balance
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
