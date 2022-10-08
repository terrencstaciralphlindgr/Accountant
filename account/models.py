import uuid
import pytz
from datetime import datetime
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from accountant.models import TimestampedModel
from accountant.methods import datetime_directive_ccxt, datetime_directive_ISO_8601
from market.models import Market, Exchange, Currency
import structlog

log = structlog.get_logger(__name__)


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

    def update(self, dic):
        """
        Update object with exchange's response after an order has been placed
        """

        if dic['datetime']:
            dt = datetime.strptime(dic['datetime'], datetime_directive_ccxt).replace(tzinfo=pytz.UTC)
        else:
            dt = None

        self.orderid = dic['id']
        self.status = dic['status']
        self.cost = dic['cost']
        self.filled = dic['filled']
        self.remaining = float(dic['remaining'])
        self.average = dic['average']
        self.fee = dic['fee']
        self.order_type = dic['type']
        self.time_in_force = dic['timeInForce']
        self.post_only = dic['postOnly']
        self.stop_price = dic['stopPrice']
        self.timestamp = dic['timestamp']
        self.last_trade_timestamp = dic['lastTradeTimestamp']
        self.trades = dic['trades']  # Only for spot orders
        self.datetime = dt
        self.response = dic
        self.save()

        log.info('Order {0} updated ({1})'.format(self.clientid, self.orderid[-4:]), account=self.account.name)


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
        unique_together = ('datetime', 'symbol', 'account',)

    def save(self, *args, **kwargs):
        return super(Trade, self).save(*args, **kwargs)

    def __str__(self):
        return self.tradeid

    def update_inventory(self):
        """
        Create new inventory object with the latest stock,
        total cost and average cost (after a new trade)
        """

        from pnl.models import Inventory
        market = self.order.market

        query = dict(
            exchange=market.exchange,
            strategy=self.order.account.strategy,
            account=self.order.account
        )

        log.bind(account=self.order.account.name, trade=self.tradeid, order=self.order.clientid)
        log.info('Update inventory')

        if market.type == 'spot':

            query['currency'] = market.base
            query['instrument'] = 0  # ASSET

            try:
                Inventory.objects.get(**query, trade=self)

            except ObjectDoesNotExist:

                # Select stock, purchase price and
                # total cost from the latest record
                qs = Inventory.objects.filter(**query)

                if qs.exists():
                    stock = qs.last().stock
                    average_cost = qs.last().average_cost
                    total_cost = qs.last().total_cost

                else:
                    stock = 0
                    total_cost = 0
                    average_cost = 0

                if self.order.side == 'buy':

                    # Calculate total_cost and new average_cost
                    stock_new = stock + self.amount  # number of items
                    total_cost_new = total_cost + self.cost  # total cost
                    average_cost_new = total_cost_new / stock_new  # cost per unit

                elif self.order.side == 'sell':

                    # Calculate total_cost and new stock
                    stock_new = max(0, stock - self.amount)
                    total_cost_new = stock_new * average_cost
                    average_cost_new = average_cost

                log.info('Total stock    {0} {1}'.format(round(stock_new, 4), market.base.code))
                log.info('Total cost     {0} {1}'.format(round(total_cost_new, 4), market.quote.code))
                log.info('Average cost   {0} {1}'.format(round(average_cost_new, 4), market.quote.code))

                Inventory.objects.create(**query,
                                         trade=self,
                                         stock=stock_new,
                                         total_cost=total_cost_new,
                                         average_cost=average_cost_new
                                         )

            else:
                log.warning('Inventory object is already created')

        elif market.type == 'perpetual':

            query['currency'] = market.margined
            query['instrument'] = 1  # CONTRACT

            try:
                Inventory.objects.get(**query, trade=self)

            except ObjectDoesNotExist:

                qs = Inventory.objects.filter(**query)

                if qs.exists():
                    stock = qs.last().stock
                    average_cost = qs.last().average_cost
                    total_cost = qs.last().total_cost

                else:
                    stock = 0
                    total_cost = 0

                if self.order.action in ['open_long', 'open_short']:

                    # Calculate total_cost and new average_cost
                    stock_new = stock + self.amount  # number of items
                    total_cost_new = total_cost + self.cost  # total cost
                    average_cost_new = total_cost_new / stock_new  # cost per unit

                elif self.order.action in ['close_long', 'close_short']:

                    # Calculate total_cost and new stock
                    stock_new = max(0, stock - self.amount)
                    total_cost_new = stock_new * average_cost
                    average_cost_new = average_cost

                log.info('Total stock    {0} {1}'.format(round(stock_new, 4), market.base.code))
                log.info('Total cost     {0} {1}'.format(round(total_cost_new, 4), market.quote.code))
                log.info('Average cost   {0} {1}'.format(round(average_cost_new, 4), market.quote.code))

                Inventory.objects.create(**query,
                                         trade=self,
                                         stock=stock_new,
                                         total_cost=total_cost_new,
                                         average_cost=average_cost_new
                                         )
            else:
                log.warning('Inventory object is already created')

        log.unbind('account', 'trade', 'order')

    def calculate_asset_pnl(self):
        """
        Create new AssetPnL object after an asset is sold.
        """

        from pnl.models import Inventory, AssetPnl
        market = self.order.market

        if self.order.side == 'sell':
            if market.type == 'spot':

                try:
                    AssetPnl.objects.get(trade=self)

                except ObjectDoesNotExist:

                    # Select purchase price from the inventory
                    # and calculate realized an unrealized pnl.
                    obj = Inventory.objects.get(trade=self)
                    purchase_price = obj.average_cost
                    sale_proceeds = self.cost  # amount_sold * price
                    realized_pnl = sale_proceeds - (self.amount * purchase_price)
                    unrealized_pnl = (obj.stock * self.price) - (obj.stock * purchase_price)

                    log.info('Sale proceeds {0} {1}'.format(round(sale_proceeds, 1), market.quote.code))
                    log.info('Sale price    {0} {1}'.format(round(self.price, 1), market.quote.code))
                    log.info('Realized PnL           {0} {1}'.format(round(realized_pnl, 1), market.quote.code))

                    AssetPnl.objects.create(
                        currency=market.base,
                        exchange=market.exchange,
                        strategy=self.order.account.strategy,
                        account=self.order.account,
                        trade=self,
                        inventory=obj,
                        sale_proceeds=sale_proceeds,
                        sale_price=self.price,
                        realized_pnl=realized_pnl,
                        unrealized_pnl=unrealized_pnl
                    )

                else:
                    log.warning('Asset Pnl already created')

    def calculate_contract_pnl(self, position_size):
        """
        Create new ContractPnL object after a position is close
        """

        from pnl.models import Inventory, ContractPnL
        market = self.order.market

        if self.order.action in ['close_long', 'close_short']:
            if market.type == 'perpetual':

                try:
                    ContractPnL.objects.get(trade=self)

                except ObjectDoesNotExist:

                    # Select average purchase price
                    obj = Inventory.objects.get(trade=self)
                    entry_price = obj.average_cost

                    exit_price = self.price
                    contracts_size = self.cost

                    if self.order.action in ['close_long']:
                        realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * contracts_size
                        realized_pnl = realized_pnl_base * exit_price
                        unrealized_pnl = position_size * (market.ticker['last'] - entry_price)

                    elif self.order.action in ['close_short']:
                        realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * (contracts_size * -1)
                        realized_pnl = realized_pnl_base * exit_price
                        unrealized_pnl = position_size * -1 * (market.ticker['last'] - entry_price)

                    log.info('Position size   {0} {1}'.format(round(contracts_size, 1), market.quote.code))
                    log.info('Entry price     {0} {1}'.format(round(entry_price, 1), market.quote.code))
                    log.info('Exit price      {0} {1}'.format(round(exit_price, 1), market.quote.code))
                    log.info('Realized PnL    {0} {1}'.format(round(realized_pnl, 1), market.quote.code))
                    log.info('Unrealized PnL  {0} {1}'.format(round(unrealized_pnl, 1), market.quote.code))

                    ContractPnL.objects.create(
                        currency=market.margined,
                        exchange=market.exchange,
                        strategy=self.order.account.strategy,
                        account=self.order.account,
                        trade=self,
                        inventory=obj,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        realized_pnl=realized_pnl,
                        unrealized_pnl=unrealized_pnl,
                        contracts_size=contracts_size
                    )

                else:
                    log.warning('Contract Pnl already created')


class Balance(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='balance', null=True)
    assets_total_value = models.FloatField(default=0)
    assets = models.JSONField(default=dict)
    open_positions = models.JSONField(default=dict)
    dt = models.DateTimeField()

    class Meta:
        verbose_name_plural = "Balances"
        unique_together = ('dt', 'account',)

    def save(self, *args, **kwargs):
        return super(Balance, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.dt.strftime(datetime_directive_ISO_8601))
