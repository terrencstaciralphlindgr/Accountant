import ccxt.pro
import structlog
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from accountant.methods import dt_aware_now, datetime_directive_ISO_8601
from accountant.models import TimestampedModel

log = structlog.get_logger(__name__)


class Exchange(TimestampedModel):

    class Rounding(models.TextChoices):
        ROUNDING = 0, "ROUNDING"
        TRUNCATE = 1, "TRUNCATE"

    class Padding(models.TextChoices):
        NOPADDING = 5, "NO_PADDING"
        PADWITHZERO = 6, "PAD_WITH_ZERO"

    name = models.CharField(max_length=20)
    exid = models.CharField(max_length=12)
    wallets = models.CharField(max_length=50, blank=True, null=True)
    properties = models.JSONField(blank=True, null=True)
    status = models.JSONField(blank=True, null=True)
    verbose = models.BooleanField(default=False)
    rounding_mode_spot = models.CharField(
        max_length=2,
        choices=Rounding.choices,
        default=Rounding.ROUNDING)
    rounding_mode_future = models.CharField(
        max_length=2,
        choices=Rounding.choices,
        default=Rounding.TRUNCATE)
    padding_mode = models.CharField(
        max_length=2,
        choices=Padding.choices,
        default=Padding.NOPADDING)
    enable_rate_limit = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Exchanges"

    def save(self, *args, **kwargs):
        return super(Exchange, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_ccxt_client(self, account=None, wallet=None):

        client = getattr(ccxt, self.exid)
        client = client({
            'verbose': self.verbose,
            'adjustForTimeDifference': True,
        })

        if account:
            client.secret = account.api_secret
            client.apiKey = account.api_key
            if 'password' in client.requiredCredentials:
                client.password = account.password

        if wallet:
            if 'defaultType' in client.options:
                client.options['defaultType'] = wallet

        return client

    def get_ccxt_client_pro(self, args=None):

        client = getattr(ccxt.pro, self.exid)

        if args:
            if 'account' in args:
                account = args['account']
                client.secret = account.api_secret
                client.apiKey = account.api_key
                if 'password' in client.requiredCredentials:
                    client.password = account.password

        return client

    def get_wallets(self):
        if self.wallets:
            return str(self.wallets).replace(" ", "").split(',')

    def is_ok(self):
        return True if self.status['status'] == 'ok' else False


class Currency(TimestampedModel):
    code = models.CharField(max_length=100, blank=True, null=True)
    exchange = models.ManyToManyField(Exchange, related_name='currency', blank=True)
    response = models.JSONField(default=dict)

    class Meta:
        verbose_name_plural = "Currencies"

    def save(self, *args, **kwargs):
        return super(Currency, self).save(*args, **kwargs)

    def __str__(self):
        return self.code

    def get_open_price(self, exchange, quote):
        if isinstance(quote, str):
            if self.code == quote:
                return 1
            from market.methods import get_market
            market, flip = get_market(exchange, base=self.code, quote=quote, wallet='spot')
            last = market.get_open_price()
            if flip:
                return 1  # /last
            return last
        else:
            raise Exception('quote must be a string')


class Market(TimestampedModel):
    instrument, symbol = [models.CharField(max_length=50) for i in range(2)]
    wallet = models.CharField(max_length=20, blank=True, null=True)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='market')
    base = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='market_base')
    quote = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='market_quote')
    margined = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='margined', null=True)
    type = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    margin = models.BooleanField(blank=True, null=True)
    contract_size, taker, maker = [models.FloatField(blank=True, null=True) for i in range(3)]
    limits, precision, info, ticker = [models.JSONField(null=True, default=dict) for i in range(4)]

    class Meta:
        verbose_name_plural = "Markets"

    def save(self, *args, **kwargs):
        return super(Market, self).save(*args, **kwargs)

    def __str__(self):
        return self.symbol + '_' + self.type[:4] + '_' + self.exchange.exid[:3]

    def is_updated(self):
        qs = Price.objects.filter(market=self).order_by('-dt')
        if qs.exists():
            last = qs.first()
            if last.dt == dt_aware_now():
                return True
        return False

    def get_open_price(self):
        qs = Price.objects.filter(market=self).order_by('-dt')
        if qs.exists():
            try:
                return qs.get(dt=dt_aware_now()).last
            except ObjectDoesNotExist:
                log.error('Open price is not updated')
        else:
            log.error('Open price object not found')


class Price(TimestampedModel):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='price')
    last = models.FloatField()
    response = models.JSONField(null=True)
    dt = models.DateTimeField(null=True)

    class Meta:
        verbose_name_plural = "Prices"

    def save(self, *args, **kwargs):
        return super(Price, self).save(*args, **kwargs)

    def __str__(self):
        return self.dt.strftime(datetime_directive_ISO_8601)
