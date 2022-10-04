from __future__ import absolute_import, unicode_literals
from billiard.process import current_process
from pprint import pprint
from accountant.celery import app
from market.methods import get_market
from account.models import Account
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

    log.info('Fetch orders')

    def create_update_delete(wallet=None):
        pass

    try:

        client = account.exchange.get_ccxt_client(account)
        wallets = account.exchange.get_wallets()
        if wallets:

            for wallet in wallets:
                client.options['defaultType'] = wallet
                response = client.fetchOrders()
                create_update_delete(wallet=wallet)

        else:
            response = client.fetchOrders()
            create_update_delete()

    except ccxt.RequestTimeout as e:
        log.error('Timeout while fetching positions...')
        raise self.retry(exc=e)

    except ccxt.NetworkError as e:
        log.error('Network error while fetching positions...')
        raise self.retry(exc=e)

    except Exception as e:
        log.exception('Fetch orders error', cause=str(e))

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
