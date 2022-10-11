from __future__ import absolute_import, unicode_literals
import pytz
from pprint import pprint
from datetime import datetime
from billiard.process import current_process
from django.core.exceptions import ObjectDoesNotExist
from accountant.methods import datetime_directive_ccxt, dt_aware_now
from accountant.celery import app
from account.models import Account, Order, Trade, Balance
from market.models import Market
from pnl.tasks import update_inventories
from celery import chord
import structlog
import ccxt
import celery

# logger = structlog.get_logger(__name__)
# logger.try_unbind('task_id', 'parent_task_id', 'request_id', 'user_id', 'ip',)
logger = structlog.wrap_logger('name')
print(logger)


@app.task(bind=True, name='Account______Fetch orders')
def fetch_orders(self, pk):
    """
    Fetch orders history
    """
    account = Account.objects.get(pk=pk)
    log = logger.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    qs = Order.objects.filter(account=account)
    start_datetime = qs.latest('datetime').datetime if qs else account.dt_created
    start_datetime = int(start_datetime.timestamp())
    params = dict(start_datetime=start_datetime)

    log.bind(start_datetime=start_datetime)
    log.info('Fetch orders')

    def create_update_order(dic, wallet=None):

        try:
            market = Market.objects.get(exchange=account.exchange, wallet=wallet, symbol=dic['symbol'])

        except ObjectDoesNotExist:
            pass

        else:

            if dic['datetime']:
                dt = datetime.strptime(dic['datetime'], datetime_directive_ccxt).replace(tzinfo=pytz.UTC)
            else:
                dt = None

            defaults = dict(
                amount=dic['amount'],
                average=dic['average'],
                clientid=dic['clientOrderId'],
                cost=dic['cost'],
                datetime=dt,
                fee=dic['fee'],
                fees=dic['fees'],
                filled=dic['filled'],
                info=dic['info'],
                market=market,
                price=dic['price'],
                remaining=dic['remaining'],
                side=dic['side'],
                status=dic['status'],
                trades=dic['trades'],
                type=dic['type'],
            )

            Order.objects.update_or_create(orderid=dic['id'],
                                           account=account,
                                           defaults=defaults
                                           )

    try:

        client = account.exchange.get_ccxt_client(account)
        wallets = account.exchange.get_wallets()
        if wallets:

            for wallet in wallets:
                client.options['defaultType'] = wallet
                response = client.fetchOrders(params=params)
                for dic in response:
                    create_update_order(dic, wallet=wallet)

        else:
            response = client.fetchOrders(params=params)
            for dic in response:
                create_update_order(dic)

    except ccxt.RequestTimeout as e:
        log.error('Fetch orders failure', cause='timeout')
        raise self.retry(exc=e)

    except ccxt.NetworkError as e:
        log.error('Fetch orders failure', cause=str(e))
        raise self.retry(exc=e)

    except Exception as e:
        log.exception('Fetch orders failure', cause=str(e))

    else:
        log.info('Fetch orders complete')


@app.task(bind=True, name='Account______Fetch trades')
def fetch_trades(self, pk):
    """
    Fetch trades history
    """
    account = Account.objects.get(pk=pk)
    log = logger.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    qs = Trade.objects.filter(account=account)
    start_datetime = qs.latest('datetime').datetime if qs else account.dt_created
    start_datetime = int(start_datetime.timestamp() * 1000)

    log.bind(start_datetime=start_datetime)

    def create_trade(dic):

        if dic['order']:
            try:
                order = Order.objects.get(orderid=dic['order'])
            except ObjectDoesNotExist:
                order = None
        else:
            order = None

        if dic['datetime']:
            dt = datetime.strptime(dic['datetime'], datetime_directive_ccxt).replace(tzinfo=pytz.UTC)
        else:
            dt = None

        defaults = dict(
            amount=dic['amount'],
            cost=dic['cost'],
            datetime=dt,
            fee=dic['fee'],
            fees=dic['fees'],
            info=dic['info'],
            order=order,
            price=dic['price'],
            side=dic['side'],
            symbol=dic['symbol'],
            taker_or_maker=dic['takerOrMaker'],
            timestamp=dic['timestamp'],
            type=dic['type']
        )

        obj, created = Trade.objects.update_or_create(tradeid=dic['id'],
                                                      account=account,
                                                      symbol=dic['symbol'],
                                                      defaults=defaults
                                                      )
        if created:
            log.info('Trade object created')

    try:

        client = account.exchange.get_ccxt_client(account)
        wallets = account.exchange.get_wallets()
        qs = Market.objects.filter(exchange=account.exchange).values_list('symbol', flat=True)

        if wallets:

            for wallet in wallets:
                client.options['defaultType'] = wallet
                symbols = (qs.filter(wallet=wallet))
                for symbol in symbols:
                    response = client.fetchMyTrades(symbol, since=start_datetime)
                    log.info('Fetch trades', length=len(response), wallet=wallet, symbol=symbol)
                    for dic in response:
                        create_trade(dic)

        else:
            symbols = list(qs)
            for symbol in symbols:
                response = client.fetchMyTrades(symbol, since=start_datetime)
                log.info('Fetch trades', length=len(response), symbol=symbol)
                for dic in response:
                    create_trade(dic)

    except ccxt.RequestTimeout as e:
        log.error('Fetch trades failure', cause='timeout')
        raise self.retry(exc=e)

    except ccxt.NetworkError as e:
        log.error('Fetch trades failure', cause=str(e))
        raise self.retry(exc=e)

    except Exception as e:
        log.exception('Fetch trades failure', cause=str(e))

    else:
        log.info('Fetch trades complete')


@app.task(bind=True, name='Account______Update inventory')
def update_inventory(self, pk):
    chord(fetch_orders.si(pk),
          fetch_trades.si(pk)
          )(update_inventories.si(pk))


@app.task(bind=True, name='Account______Bulk Update inventory')
def bulk_update_inventory(self):
    for account in Account.objects.all():
        pk = account.pk
        chord(fetch_orders.si(pk),
              fetch_trades.si(pk)
              )(update_inventories.si(pk))
