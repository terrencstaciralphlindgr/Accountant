from __future__ import absolute_import, unicode_literals
import structlog
from billiard.process import current_process
from account.models import Account, Trade
from accountant.methods import datetime_directive_ISO_8601
from accountant.celery import app
from pnl.models import Inventory

from market.models import Exchange, Market, Currency

log = structlog.get_logger(__name__)


@app.task(bind=True, name='PnL_____Update_asset_inventory')
def update_asset_inventory(self, pk):
    """
    Update asset inventory
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    entries = Inventory.objects.filter(account=account, instrument=0)
    if entries.exists():
        start_datetime = entries.latest('datetime').datetime
    else:
        start_datetime = account.dt_created

    log.bind(start_datetime=start_datetime.strftime(datetime_directive_ISO_8601))
    log.info('Update assets inventory')

    # Select trades and iterate
    trades = Trade.objects.filter(account=account,
                                  order__market__type='spot',
                                  datetime__gt=start_datetime
                                  ).order_by('datetime')
    if trades.exists():

        for index, trade in enumerate(trades):

            log.bind(trade=trade.tradeid,
                     amount=trade.amount,
                     side=trade.side)

            log.info('Create new entry')
            entry = Inventory.objects.create(account=account,
                                             exchange=account.exchange,
                                             currency=trade.order.market.base,
                                             trade=trade,
                                             instrument=0,
                                             datetime=trade.datetime)

            # Determine stock, total and average costs from previous inventory entry

            if entries.exists() or index > 0:
                prev_dt = trades[index-1].datetime if index > 0 else start_datetime
                prev = Inventory.objects.get(account=account, datetime=prev_dt, instrument=0)
                prev_stock = prev.stock
                prev_total_cost = prev.total_cost
                prev_average_cost = prev.average_cost

            else:
                prev_stock, prev_total_cost, prev_average_cost = [0 for i in range(3)]

            # Determine stock, total and average costs

            if trade.side == 'buy':
                entry.stock = prev_stock + trade.amount
                entry.total_cost = prev_total_cost + trade.cost
                entry.average_cost = entry.total_cost / entry.stock

            elif trade.side == 'sell':
                if trade.amount > prev_stock:
                    log.warning('Non-inventoried asset sold')
                    entry.stock = 0
                    entry.total_cost = 0
                else:
                    entry.stock = prev_stock - trade.amount
                    entry.total_cost = entry.stock * prev_average_cost

                entry.average_cost = prev_average_cost

                # Calculate realized PnL

                purchase_price = prev_average_cost
                purchase_cost = trade.amount * purchase_price  # cost of the asset
                proceed = trade.cost  # cash received from the sale of asset
                entry.realized_pnl = proceed - purchase_cost

                # Calculate unrealized PnL

                stock_value_current_price = entry.stock * trade.price  # stock value at the current price
                stock_value_purchase_price = entry.stock * purchase_price
                entry.unrealized_pnl = stock_value_current_price - stock_value_purchase_price

            entry.save()

    else:
        log.info('Update assets inventory no required')
        return

    log.info('Update assets inventory complete')


@app.task(bind=True, name='PnL_____Update_contract_inventory')
def update_contract_inventory(self, pk):
    """
    Update contract inventory
    """
    account = Account.objects.get(pk=pk)
    log.bind(account=account.name)
    if self.request.id:
        log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    entries = Inventory.objects.filter(account=account, instrument=1)
    if entries.exists():
        start_datetime = entries.latest('datetime').datetime
    else:
        start_datetime = account.dt_created

    log.bind(start_datetime=start_datetime.strftime(datetime_directive_ISO_8601))
    log.info('Update contracts inventory')

    # Select trades and iterate
    trades = Trade.objects.filter(account=account,
                                  order__market__type='perpetual',
                                  datetime__gt=start_datetime
                                  ).order_by('datetime')
    if trades.exists():

        for index, trade in enumerate(trades):

            log.bind(trade=trade.tradeid,
                     amount=trade.amount,
                     side=trade.side)

            log.info('Create new entry')
            entry = Inventory.objects.create(account=account,
                                             exchange=account.exchange,
                                             currency=trade.order.market.base,
                                             trade=trade,
                                             instrument=1,
                                             datetime=trade.datetime)

            # Determine stock, total and average costs from previous inventory entry

            if entries.exists() or index > 0:
                prev_dt = trades[index-1].datetime if index > 0 else start_datetime
                prev = Inventory.objects.get(account=account, datetime=prev_dt, instrument=1)
                prev_stock = prev.stock
                prev_total_cost = prev.total_cost
                prev_average_cost = prev.average_cost

            else:
                prev_stock, prev_total_cost, prev_average_cost = [0 for i in range(3)]

            if trade.side == 'buy':

                # Close short
                if prev_stock < 0:

                    entry.stock = prev_stock + trade.amount
                    entry.total_cost = entry.stock * prev_average_cost  # decrease
                    entry.average_cost = prev_average_cost

                    # Determine realized and unrealized profit and loss for USDⓈ-margined contracts
                    # https://www.binance.com/en/support/faq/3a55a23768cb416fb404f06ffedde4b2

                    # Directives
                    position_size = trade.cost
                    exit_price = trade.price
                    mark_price = trade.price
                    entry_price = entry.average_cost

                    realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * (position_size * -1)
                    entry.realized_pnl = realized_pnl_base * exit_price
                    entry.unrealized_pnl = position_size * -1 * (mark_price - entry_price)

                # Open long
                elif prev_stock > 0:

                    entry.stock = prev_stock + trade.amount
                    entry.total_cost = prev_total_cost + trade.cost  # increase
                    entry.average_cost = entry.total_cost / entry.stock

                    # No PnL calculation

            elif trade.side == 'sell':

                # Open short
                if prev_stock < 0:

                    entry.stock = prev_stock - trade.amount  # allow negative stock to distinguish open and close
                    entry.total_cost = prev_total_cost + trade.cost  # increase
                    entry.average_cost = entry.total_cost / abs(entry.stock)

                    # No PnL calculation

                # Close long
                elif prev_stock > 0:

                    entry.stock = prev_stock - trade.amount
                    entry.total_cost = entry.stock * prev_average_cost  # decrease
                    entry.average_cost = prev_average_cost

                    # Determine realized and unrealized profit and loss for USDⓈ-margined contracts
                    # https://www.binance.com/en/support/faq/3a55a23768cb416fb404f06ffedde4b2

                    # Directives
                    position_size = trade.cost
                    exit_price = trade.price
                    mark_price = trade.price
                    entry_price = entry.average_cost

                    realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * position_size
                    entry.realized_pnl = realized_pnl_base * exit_price
                    entry.unrealized_pnl = position_size * 1 * (mark_price - entry_price)

            entry.save()

    else:
        log.info('Update contracts inventory no required')
        return

    log.info('Update contracts inventory complete')
