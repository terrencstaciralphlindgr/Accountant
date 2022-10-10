from __future__ import absolute_import, unicode_literals
from pprint import pprint
from _datetime import datetime, timezone
import ccxt
import ccxt.pro
import asyncio
import subprocess
import requests
import urllib3
import structlog
from billiard.process import current_process
from django.db.utils import OperationalError
from django.core.exceptions import ObjectDoesNotExist, SynchronousOnlyOperation
from django.db import close_old_connections
from celery import Task
from accountant.settings import EXCHANGES
from accountant.celery import app
from market.models import Exchange, Market, Currency
from market.methods import get_market

logger = structlog.get_logger(__name__)


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
                    if code in EXCHANGES[exid]['supported_quote'] or \
                            code in EXCHANGES[exid]['supported_base']:
                        update(code, dic)

        else:
            client.load_markets(True)
            for code, dic in client.currencies.items():
                if code in EXCHANGES[exid]['supported_quote'] or \
                        code in EXCHANGES[exid]['supported_base']:
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

            if quote in EXCHANGES[exid]['supported_quote'] and \
                    base in EXCHANGES[exid]['supported_base']:

                try:
                    Currency.objects.get(exchange=exchange, code=base)
                    Currency.objects.get(exchange=exchange, code=quote)

                # Abort if a currency is unknown
                except ObjectDoesNotExist:
                    log.warning('A currency is not supported for market {0}'.format(market))
                    return

                else:

                    if quote in EXCHANGES[exid]['supported_quote']:

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


@app.task(bind=True, name='Market______Websocket loop')
def ws_loops(self):
    """
    Establish websocket streams with exchanges and collect tickers price
    """

    if self.request.id:
        log = logger.bind(worker=current_process().index, task=self.request.id[:3])

    try:

        async def method_loop(client, exid, wallet, method, private, args):

            log = logger.bind()
            if wallet:
                log = log.bind(wallet=wallet)

            if private:
                account = args['account']
                client.secret = account.api_secret
                client.apiKey = account.api_key
                log.info('Stream', account=account.name, method=method, exid=exid, key=client.apiKey[:4])

            else:
                symbol = args['symbol']
                market = args['market']
                log.info('Stream', symbol=symbol, method=method, exid=exid)

            while True:

                try:
                    if private:

                        response = await getattr(client, method)()

                        if method == 'watchMyTrades':
                            log.info('Trade event', account=account.name, key=client.apiKey[:4])
                            insert_trade_event.delay(account.pk, response)

                        elif method == 'watchOrders':
                            log.info('Order event', account=account.name, key=client.apiKey[:4])
                            insert_order_event.delay(account.pk, response)

                    else:

                        response = await getattr(client, method)(symbol)
                        if method == 'watch_ticker':

                            # log_ws.info(response['last'], symbol=response['symbol'])

                            try:
                                # Save ticker price every 5 sec.
                                save_ticker_price(market, response, freq=5)

                                if not market.is_updated():
                                    log = log.bind(dt=dt_aware_now().strftime(datetime_directive_ISO_8601),
                                                   market=market.type,
                                                   last=response['last'])

                                    Price.objects.create(market=market,
                                                         response=response,
                                                         dt=dt_aware_now(),
                                                         last=response['last']
                                                         )
                                    log.info('Price object created')

                            except Exception as e:
                                log.error(traceback.format_exc())
                                log.exception(str(e))

                            else:
                                pass

                    if not private:
                        await asyncio.sleep(2)

                except ccxt.NetworkError as e:

                    log.error('Stream disconnection', cause=str(e), method=method)

                    log.warning('Revoke task', task_id=self.request.id)
                    app.control.revoke(self.request.id, terminate=True, signal='SIGKILL')

                    log.info('Restart containers...')
                    cmd = '/usr/local/bin/docker-compose restart'
                    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

                except Exception as e:
                    log.error('Stream disconnection', cause=str(e))
                    break

            await client.close()

        async def clients_loop(loop, dic):

            exid, wallet, method, private, args = dic.values()

            # Initialize exchange CCXT instance
            exchange = Exchange.objects.get(exid=exid)
            client = getattr(ccxt.pro, exchange.exid)
            client = client(dict(enableRateLimit=True,
                                 asyncio_loop=loop,
                                 newUpdates=True
                                 ))

            if wallet:
                if 'defaultType' in client.options:
                    client.options['defaultType'] = wallet

            # Close PostgreSQL connections
            close_old_connections()

            await asyncio.gather(method_loop(client, exid, wallet, method, private, args))
            await client.close()

        async def main(loop):

            lst = []
            exchanges = EXCHANGES.keys()

            for exid in exchanges:
                exchange = Exchange.objects.get(exid=exid)

                for wallet_key in EXCHANGES[exid].keys():
                    wallet = None if wallet_key == 'default' else wallet_key

                    # Append markets loops
                    for instrument in EXCHANGES[exid][wallet_key]['markets']['instruments']:
                        for method in EXCHANGES[exid][wallet_key]['markets']['methods']:
                            market = get_market(exchange,
                                                base=instrument['base'],
                                                quote=instrument['quote'],
                                                tp=instrument['type']
                                                )[0]

                            lst.append(dict(exid=exid,
                                            wallet=wallet,
                                            method=method,
                                            private=False,
                                            args=dict(symbol=market.symbol,
                                                      market=market
                                                      )
                                            )
                                       )

            # Close PostgreSQL connections
            close_old_connections()

            loops = [clients_loop(loop, dic) for dic in lst]

            try:
                await asyncio.gather(*loops)

            except Exception as e:
                log.exception(str(e))
            else:
                pass

        loop = asyncio.new_event_loop()
        loop.run_until_complete(main(loop))

    except SynchronousOnlyOperation as e:
        log.error('Stream establishment failed !', cause=str(e))

    except OperationalError as e:
        log.error('Operational error', cause=str(e))

    except Exception as e:
        log.error('Unknown exception', cause=str(e))

