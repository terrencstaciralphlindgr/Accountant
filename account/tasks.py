from __future__ import absolute_import, unicode_literals
import pytz
from datetime import datetime
from billiard.process import current_process
from django.core.exceptions import ObjectDoesNotExist
from accountant.methods import datetime_directive_ccxt
from accountant.celery import app
from account.models import Account, Order, Trade
from market.models import Market
import structlog
import ccxt

log = structlog.get_logger(__name__)


@app.task(bind=True, name='Account______Fetch orders')
def fetch_orders(self, pk):
    """
    Fetch an account asset balance
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    qs = Order.objects.filter(account=account)
    start_datetime = qs.latest('datetime') if qs else account.dt_created
    params = dict(start_datetime=start_datetime)

    log.bind(start_datetime=start_datetime)
    log.info('Fetch orders')

    def create_update(dic, wallet=None):

        try:
            market = Market.objects.get(exchange=account.exchange, symbol=dic['symbol'])

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
                    create_update(dic, wallet=wallet)

        else:
            response = client.fetchOrders(params=params)
            for dic in response:
                create_update(dic)

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
    Fetch trades
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    def create_update_delete(wallet=None):
        pass

    try:

        client = account.exchange.get_ccxt_client(account)
        wallets = account.exchange.get_wallets()
        if wallets:

            for wallet in wallets:
                client.options['defaultType'] = wallet
                response = client.fetchTrades()
                create_update_delete(wallet=wallet)

        else:
            response = client.fetchTrades()
            create_update_delete()

    except ccxt.RequestTimeout as e:
        log.error('Timeout while fetching trades...')
        raise self.retry(exc=e)

    except ccxt.NetworkError as e:
        log.error('Network error while fetching trades...')
        raise self.retry(exc=e)

    except Exception as e:
        log.exception('Fetch trades error', cause=str(e))

    else:
        log.info('Fetch trades complete')
