from __future__ import absolute_import, unicode_literals
from pprint import pprint
from _datetime import datetime, timezone
import ccxt
import requests
import urllib3
import structlog
from django.core.exceptions import ObjectDoesNotExist
from celery import Task
from accountant.settings import EXCHANGES
from accountant.celery import app

from market.models import Exchange, Market, Currency

log = structlog.get_logger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (ccxt.DDoSProtection,
                     ccxt.RateLimitExceeded,
                     ccxt.RequestTimeout,
                     ccxt.NetworkError,
                     urllib3.exceptions.ReadTimeoutError,
                     requests.exceptions.ReadTimeout)

    retry_kwargs = {'max_retries': 5, 'default_retry_delay': 3}
    retry_backoff = True
    retry_backoff_max = 30
    retry_jitter = False


@app.task(name='Markets_____Update_exchange_currencies')
def bulk_update_currencies():
    for exid in EXCHANGES.keys():
        update_currencies.delay(exid)


@app.task(name='Markets_____Update_exchange_markets')
def bulk_update_markets():
    for exid in EXCHANGES.keys():
        update_markets.delay(exid)


@app.task(name='Markets_____Update_exchange_status')
def bulk_update_status():
    for exid in EXCHANGES.keys():
        update_status.delay(exid)


@app.task(base=BaseTaskWithRetry)
def update_status(exid):
    """
    Fetch exchange status and update self.status dictionary
    """

    log.info('Update status', exid=exid)

    try:

        exchange = Exchange.objects.get(exid=exid)
        if not isinstance(exchange.status, dict):
            exchange.status = dict()

        try:
            status = exchange.get_ccxt_client().fetchStatus()

        except Exception as e:
            exchange.status['status'] = 'nok'
            exchange.status['updated'] = datetime.now(timezone.utc)
            exchange.status['exception'] = str(e)
            exchange.save()

        else:
            exchange.status = status
            exchange.save()

    except ObjectDoesNotExist:
        log.error('Exchange is not created')

    else:
        pass


@app.task(base=BaseTaskWithRetry)
def update_currencies(exid):
    """
    Fetch currencies listed in the exchange and create/delete Currency
    """
    log.info('Update currencies', exid=exid)

    try:

        exchange = Exchange.objects.get(exid=exid)
        client = exchange.get_ccxt_client()

        def update(code, dic):

            try:
                obj = Currency.objects.get(code=code, exchange=exchange)

            # Currency isn't listed on the exchange
            except ObjectDoesNotExist:
                try:
                    obj = Currency.objects.get(code=code)

                # Currency isn't in database
                except ObjectDoesNotExist:

                    log.info('Create new currency {0}'.format(code))
                    obj = Currency.objects.create(code=code)

            # Declare the currency as listed on the exchange
            obj.exchange.add(exchange)
            obj.response[exid] = dic
            obj.save()

            log.info('{0} is now listed in {1}'.format(code, exchange.name))

        if exchange.wallets and exid != 'okex':

            for wallet in exchange.get_wallets():
                try:
                    client.options['defaultType'] = wallet
                    client.load_markets(True)

                except Exception as e:
                    raise Exception('Currencies update failure: {0}'.format(e))

            else:
                for code, dic in client.currencies.items():
                    if code in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_QUOTE'] or \
                            code in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_BASE']:
                        update(code, dic)

        else:
            client.load_markets(True)
            for code, dic in client.currencies.items():
                if code in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_QUOTE'] or \
                        code in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_BASE']:
                    update(code, dic)

        log.info('Task complete', exid=exid)

    except ObjectDoesNotExist:
        log.error('Exchange is not created')

    else:
        pass


@app.task(base=BaseTaskWithRetry)
def update_markets(exid):
    """
    Fetch exchange markets and update Market
    """

    log.info('Update market', exid=exid)

    try:

        exchange = Exchange.objects.get(exid=exid)

        def update():

            base, quote = response['base'], response['quote']

            if quote in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_QUOTE'] and \
                    base in bookkeeper.settings.EXCHANGES[exid]['SUPPORTED_BASE']:

                try:
                    Currency.objects.get(exchange=exchange, code=base)
                    Currency.objects.get(exchange=exchange, code=quote)

                # Abort if a currency is unknown
                except ObjectDoesNotExist:
                    log.warning('A currency is not supported for market {0}'.format(market))
                    return

                else:

                    if quote in EXCHANGES[exid]['SUPPORTED_QUOTE']:

                        tp = response['type'] if 'type' in response else None
                        swap = response['swap'] if 'swap' in response else None
                        spot = response['spot'] if 'spot' in response else None
                        option = response['option'] if 'option' in response else None
                        delivery = response['delivery'] if 'delivery' in response else None

                        if swap:
                            tp = 'perpetual'
                        elif delivery:
                            tp = 'delivery'
                        elif option:
                            return

                        # Exchange specific
                        if exid == 'binance' and swap:
                            if response['info']['contractType'] != 'PERPETUAL':
                                tp = 'delivery'
                        if exid == 'ftx' and tp == 'future':
                                tp = 'delivery'

                        # Abort is delivery
                        if tp == 'delivery':
                            return

                        if spot:
                            margined = None
                        else:
                            margined = Currency.objects.get(exchange=exchange, code=response['settle'])

                        defaults = {
                            'type': tp,
                            'instrument': response['id'],
                            'quote': Currency.objects.get(exchange=exchange, code=quote),
                            'base': Currency.objects.get(exchange=exchange, code=base),
                            'margined': margined,
                            'margin': response['margin'],
                            'active': response['active'],
                            'contract_size': response['contractSize'],
                            'taker': response['taker'],
                            'maker': response['maker'],
                            'limits': response['limits'],
                            'precision': response['precision'],
                            'info': response
                        }

                        # create or update market object
                        obj, created = Market.objects.update_or_create(exchange=exchange,
                                                                       wallet=wallet,
                                                                       symbol=response['symbol'],
                                                                       defaults=defaults
                                                                       )
                        if created:
                            log.info('Create new market {0} {1}'.format(tp, response['symbol']))

        if exchange.is_ok():
            client = exchange.get_ccxt_client()
            if exchange.wallets:

                for wallet in exchange.get_wallets():
                    try:
                        client.options['defaultType'] = wallet
                        client.load_markets(True)

                    except Exception as e:
                        raise Exception('Market update failure: {0}'.format(e))

                    else:
                        log.info('Update {0} {1} markets'.format(exchange.name, wallet))
                        for market, response in client.markets.items():
                            update()

                        unlisted = Market.objects.filter(exchange=exchange, wallet=wallet).exclude(
                            symbol__in=list(client.markets.keys())
                        )
                        if unlisted:
                            log.info('Unlist {0} market(s)'.format(unlisted.count()))
                            unlisted.delete()

            else:
                wallet = None
                log.info('Update {0} markets'.format(exchange.name))

                client.load_markets(True)
                for market, response in client.markets.items():
                    update()

                unlisted = Market.objects.filter(exchange=exchange).exclude(symbol__in=list(client.markets.keys()))
                if unlisted:
                    log.info('Unlist {0} market(s)'.format(unlisted.count()))
                    unlisted.delete()

        log.info('Task complete', exid=exid)

    except ObjectDoesNotExist:
        log.error('Exchange is not created')

    else:
        pass
