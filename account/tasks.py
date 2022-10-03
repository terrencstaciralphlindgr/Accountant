from __future__ import absolute_import, unicode_literals
from billiard.process import current_process
from pprint import pprint
from accountant.celery import app
from market.methods import get_market
from account.models import Account
import structlog
import ccxt

log = structlog.get_logger(__name__)


@app.task(bind=True, name='Account______Fetch balance')
def fetch_account_balance(self, pk):
    """
    Fetch an account asset balance
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.info('Request ID')
        log.bind(worker=current_process().index, task=self.request.id[:3])

    log.info('Fetch balance')

    def create_update_delete(wallet=None):

        for code in response['total']:
            if response['total'][code]:
                if code in [account.strategy.base.code, account.quote.code]:
                    obj = get_asset(account, code, wallet)
                    obj.total = response['total'][code]
                    obj.free = response['free'][code]
                    obj.used = response['used'][code]
                    obj.save()

        # Clean exchange info into account object
        if account.exchange.exid == 'ftx':
            response['info']['result'] = [i for i in response['info']['result'] if float(i['total']) != 0]
        if account.exchange.exid == 'binance' and wallet == 'spot':
            response['info']['balances'] = [i for i in response['info']['balances'] if float(i['free']) != 0]
        if account.exchange.exid == 'binance' and wallet == 'future':
            response['info']['assets'] = [i for i in response['info']['assets'] if float(i['walletBalance']) != 0]
            response['info']['positions'] = [i for i in response['info']['positions'] if float(i['positionAmt']) != 0]

        key = wallet if account.exchange.get_wallets() else 'main'
        account.info[key] = response['info']
        account.save()

        # Delete objects
        for obj in Asset.objects.filter(account=account, wallet=wallet):
            if obj.currency.code not in [account.strategy.base.code, account.quote.code]:
                log.info('Delete object {0}_{1}'.format(obj.currency.code, obj.wallet))
                obj.delete()

    try:

        client = account.exchange.get_ccxt_client(account)
        wallets = account.exchange.get_wallets()
        if wallets:

            for wallet in wallets:
                client.options['defaultType'] = wallet
                response = client.fetch_balance()
                create_update_delete(wallet=wallet)

        else:
            response = client.fetch_balance()
            create_update_delete()

        # Calculate assets value
        for obj in Asset.objects.filter(account=account):

            if obj.currency == account.quote:
                price = 1
            else:
                price = account.base_price

            obj.total_value = obj.total * price
            obj.free_value = obj.free * price
            if obj.used:
                obj.used_value = obj.used * price
            obj.save()

        # Assets weight
        account_total_value = account.assets_df().total_value.sum()
        for obj in Asset.objects.filter(account=account):
            if obj.currency.code != account.quote:
                obj.weight = round((obj.total_value / account_total_value) * 100, 2)
                obj.save()

    except Exception as e:
        log.exception('Fetch balance error', cause=str(e))

    else:
        log.info('Fetch balance complete')


@app.task(bind=True, name='Account______Fetch position')
def fetch_positions(self, pk):
    """
    Fetch open positions
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.info('Request ID')
        log.bind(worker=current_process().index, task=self.request.id[:3])

    client = account.exchange.get_ccxt_client(account)
    if account.exchange.get_wallets():
        client.options['defaultType'] = 'future'

    log.info('Fetch position')

    try:
        if client.has['fetchPositions']:
            response = client.fetchPositions()
        else:
            raise Exception('fetchPositions not supported')

    except ccxt.RequestTimeout as e:
        log.error('Timeout while fetching positions...')
        raise self.retry(exc=e)

    except ccxt.NetworkError as e:
        log.error('Network error while fetching positions...')
        raise self.retry(exc=e)

    else:

        market, flip = get_market(account.exchange,
                                  base=account.strategy.base.code,
                                  quote=account.quote.code,
                                  tp='perpetual'
                                  )
        positions = [i for i in response if i['symbol'] == market.symbol and float(i['contracts']) != 0]
        if positions:
            for dic in positions:
                if dic['contracts']:
                    log.info('Position {0} is open ({1})'.format(dic['symbol'], dic['side']))

                    # Exchange specific
                    if account.exchange.exid == 'ftx':
                        dic['collateral'] = account.free_quantity('USD')
                        dic['unrealizedPnl'] = float(dic['info']['recentPnl'])

                    default = dict(
                        timestamp=dic['timestamp'],
                        datetime=dic['datetime'],
                        initial_margin=dic['initialMargin'],
                        initial_margin_pct=dic['initialMarginPercentage'],
                        maint_margin=dic['maintenanceMargin'],
                        maint_margin_pct=dic['maintenanceMarginPercentage'],
                        entry_price=dic['entryPrice'],
                        notional=dic['notional'],
                        leverage=dic['leverage'],
                        unrealized_pnl=dic['unrealizedPnl'],
                        contracts=dic['contracts'],
                        contract_size=dic['contractSize'],
                        margin_ratio=dic['marginRatio'],
                        liquidation_price=dic['liquidationPrice'],
                        mark_price=dic['markPrice'],
                        collateral=dic['collateral'],
                        margin_mode=dic['marginMode'],
                        side=dic['side'],
                        percentage=dic['percentage'],
                        response=dic
                    )

                    obj, created = Position.objects.update_or_create(
                        exchange=account.exchange,
                        account=account,
                        market=market,
                        defaults=default
                    )

                    if created:
                        log.info('Position created')
                    else:
                        log.info('Position updated')

        # Delete closed positions
        for obj in Position.objects.filter(account=account):
            if not positions or obj.market.symbol not in [dic['symbol'] for dic in positions]:
                log.info('Delete closed position {0}'.format(obj.market.symbol))
                obj.delete()

        # Positions weight
        account_total_value = account.assets_df().total_value.sum()
        for obj in Position.objects.filter(account=account):
            obj.weight = round((abs(obj.notional) / account_total_value) * 100, 2)
            obj.save()

    log.info('Fetch position complete')
