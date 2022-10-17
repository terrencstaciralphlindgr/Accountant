import uuid
from datetime import datetime
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from accountant.models import TimestampedModel
from accountant.methods import datetime_directive_ISO_8601, get_start_datetime, dt_aware_now
from market.models import Market, Exchange, Currency
from market.methods import get_market
import structlog

logger = structlog.get_logger(__name__)


class Account(TimestampedModel):
    name = models.CharField(max_length=20)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='account', null=True)
    quote = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='account_quote', null=True)
    api_key, api_secret = [models.CharField(max_length=100, blank=True) for i in range(2)]
    password = models.CharField(max_length=100, null=True, blank=True)
    response = models.JSONField(default=dict, blank=True)
    info = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Accounts"

    def save(self, *args, **kwargs):

        if self.response:
            if 'name' in self.response:
                self.name = self.response['name']

        if not self.pk:
            pass

        return super(Account, self).save(*args, **kwargs)

    def __str__(self):
        if self.name:
            return self.name
        return str(self.pk)

    def cumulated_realized_pnl(self, period):
        from pnl.models import Inventory
        dt = get_start_datetime(self, period)
        qs = Inventory.objects.filter(account=self, datetime__gte=dt)
        return qs.aggregate(models.Sum('realized_pnl'))['realized_pnl__sum']

    def growth(self, period):
        dt = get_start_datetime(self, period)
        try:
            initial_asset_value = Balance.objects.get(dt=dt)
        except ObjectDoesNotExist:
            return 'Not data'
        else:

            cumulated_realized_pnl = self.realized_pnl(period)

            return dict(
                period=period,
                initial_asset_value=initial_asset_value,
                cumulated_realized_pnl=cumulated_realized_pnl,
                growth_rate=cumulated_realized_pnl / initial_asset_value
            )

    def current_exposition(self):

        code = 'BTC'
        balance = Balance.objects.filter(account=self).latest('dt')

        # Select asset value
        asset = balance.get_assets_value()
        assets_value_total = asset['assets_total_value']
        exposition_value = asset[code]['value']['total']

        # Select position value
        pos = balance.get_position_value()
        if 'position_value' in pos:
            exposition_value += pos['position_value']

        # Determine side
        side = 'long' if exposition_value > 0 else 'short'

        return dict(side=side,
                    code=code,
                    exposition=exposition_value/assets_value_total
                    )


class Order(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='order', null=True, db_index=True)
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='order', null=True, db_index=True)
    orderid = models.CharField(max_length=150, null=True, db_index=True)
    clientid = models.CharField(max_length=150, null=True, db_index=True)
    status, type = [models.CharField(max_length=150, null=True) for i in range(2)]
    amount, remaining = [models.FloatField(max_length=10, null=True) for i in range(2)]
    filled = models.FloatField(max_length=10, null=True, default=0)
    side = models.CharField(max_length=10, null=True, choices=(('buy', 'buy'), ('sell', 'sell')))
    cost = models.FloatField(null=True)
    average, price = [models.FloatField(null=True, blank=True) for i in range(2)]
    fee, trades, fees, info = [models.JSONField(null=True, default=dict) for i in range(4)]
    datetime = models.DateTimeField(null=True)
    timestamp, last_trade_timestamp = [models.BigIntegerField(null=True) for i in range(2)]

    class Meta:
        verbose_name_plural = "Orders"
        permissions = [
            ("cancel_order", "Can cancel an open order"),
        ]

    def save(self, *args, **kwargs):
        return super(Order, self).save(*args, **kwargs)

    def __str__(self):
        if self.clientid:
            return self.clientid
        else:
            return str(self.id)


class Trade(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='trade', null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='trade', blank=True, null=True)
    tradeid = models.CharField(max_length=200)
    symbol = models.CharField(max_length=20)
    side, type, taker_or_maker = [models.CharField(max_length=20, blank=True, null=True) for i in range(3)]
    datetime = models.DateTimeField()
    timestamp = models.BigIntegerField()
    price = models.FloatField()
    amount = models.FloatField()
    cost = models.FloatField()
    fee, fees, info = [models.JSONField(default=dict, null=True, blank=True) for i in range(3)]

    class Meta:
        verbose_name_plural = "Trades"
        unique_together = ('datetime', 'tradeid', 'symbol', 'account',)

    def save(self, *args, **kwargs):
        return super(Trade, self).save(*args, **kwargs)

    def __str__(self):
        return self.tradeid


class Balance(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='balance', null=True)
    assets_total_value = models.FloatField(default=0)
    assets = models.JSONField(default=dict)
    open_position = models.JSONField(default=dict, blank=True, null=True)
    dt = models.DateTimeField()

    class Meta:
        verbose_name_plural = "Balances"
        unique_together = ('dt', 'account',)

    def save(self, *args, **kwargs):
        return super(Balance, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.dt.strftime(datetime_directive_ISO_8601))

    def get_assets_value(self):
        """
        Return assets value with the latest ticker price
        """
        log = logger.bind(account=self.account.name)
        log.info('Get latest assets value')

        dic = dict()
        quote = self.account.quote.code
        for code in self.assets.keys():

            dic[code] = dict()
            dic[code]['value'] = dict()
            dic[code]['quantity'] = dict()

            if code != quote:
                market, flip = get_market(self.account.exchange, base=code, quote=quote, tp='spot')
                last = market.ticker['last']

            else:
                last = 1

            for key in ['total', 'free', 'used']:
                dic[code]['quantity'][key] = self.assets[code]['quantity'][key]
                dic[code]['value'][key] = self.assets[code]['quantity'][key] * last

        # Calculate total assets value
        dic['assets_total_value'] = sum([dic['total'] for dic in [k['value'] for k in [v for v in dic.values()]]])
        dic['last_update'] = datetime.utcnow().strftime(datetime_directive_ISO_8601)

        return dic

    def get_position_value(self):
        """
        Return notional value of open positions with the latest ticker price
        """
        log = logger.bind(account=self.account.name)
        log.info('Get latest position value')

        if 'side' in self.open_position:

            side = self.open_position['side']
            contacts = self.open_position['contracts']
            symbol = self.open_position['market__symbol']

            # Get last price
            market, flip = get_market(self.account.exchange, symbol=symbol)
            last = market.ticker['last']

            position_value = contacts * last if side == 'buy' else -contacts * last

            return dict(
                side=self.open_position['side'],
                notional=self.open_position['contracts'] * last,
                position_value=position_value,
                last_update=datetime.utcnow().strftime(datetime_directive_ISO_8601)
            )

        else:
            return dict()
