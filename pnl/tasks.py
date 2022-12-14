from __future__ import absolute_import, unicode_literals
import structlog
from billiard.process import current_process
from account.models import Account, Trade
from accountant.methods import datetime_directive_ISO_8601
from accountant.celery import app
from pnl.models import Inventory
import logging
from celery.utils.log import get_task_logger
from celery import group, chain

# log = get_task_logger(__name__)

log = structlog.wrap_logger(get_task_logger(__name__))
# log = get_task_logger(__name__)


@app.task(bind=True, name='PnL_____Update_asset_inventory')
def update_asset_inventory(self, pk):
    """
    Update asset inventory
    """

    account = Account.objects.get(pk=pk)
    # log = logger.bind(account=account.name)

    if self.request.id:
        pass
        # log = log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    entries = Inventory.objects.filter(account=account, instrument=0)
    if entries.exists():
        prev_entries = True
        latest = entries.latest('datetime')
        start_datetime = latest.datetime
    else:
        prev_entries = False
        start_datetime = account.dt_created

    # log = log.bind(start_datetime=start_datetime.strftime(datetime_directive_ISO_8601))
    log.info('Update assets inventory')

    # Select trades and iterate
    trades = Trade.objects.filter(account=account,
                                  order__market__type='spot',
                                  datetime__gt=start_datetime
                                  ).order_by('dt_created')
    if trades.exists():

        for index, trade in enumerate(trades):

            # log = log.bind(trade=trade.tradeid,
            #                amount=trade.amount,
            #                side=trade.side)

            log.info('Create new entry')
            entry = Inventory.objects.create(account=account,
                                             exchange=account.exchange,
                                             currency=trade.order.market.base,
                                             trade=trade,
                                             instrument=0,
                                             datetime=trade.datetime)

            # Determine stock, total and average costs from previous inventory entry
            if prev_entries or index > 0:
                prev = Inventory.objects.get(account=account, trade=trades[index - 1], instrument=0) if index > 0 \
                    else latest
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
                    log.info('Non-inventoried asset sold')
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
    # log = logger.bind(account=account.name)

    if self.request.id:
        pass
        # log = log.bind(worker=current_process().index, task=self.request.id[:3])

    # Determine start datetime
    entries = Inventory.objects.filter(account=account, instrument=1)
    if entries.exists():
        prev_entries = True
        latest = entries.latest('datetime')
        start_datetime = latest.datetime
    else:
        prev_entries = False
        start_datetime = account.dt_created

    # log_cont.bind(start_datetime=start_datetime.strftime(datetime_directive_ISO_8601))
    # log_cont.info('Update contracts inventory')

    # Select trades and iterate
    trades = Trade.objects.filter(account=account,
                                  order__market__type='perpetual',
                                  datetime__gt=start_datetime
                                  ).order_by('dt_created')
    if trades.exists():

        for index, trade in enumerate(trades):

            # log = log.bind(trade=trade.tradeid,
            #                amount=trade.amount,
            #                side=trade.side)

            log.info('Create new entry')
            entry = Inventory.objects.create(account=account,
                                             exchange=account.exchange,
                                             currency=trade.order.market.base,
                                             trade=trade,
                                             instrument=1,
                                             datetime=trade.datetime)

            # Determine stock, total and average costs from previous inventory entry
            if prev_entries or index > 0:
                prev = Inventory.objects.get(account=account, trade=trades[index - 1], instrument=1) if index > 0 \
                    else latest
                prev_stock = prev.stock
                prev_total_cost = prev.total_cost
                prev_average_cost = prev.average_cost

            else:
                prev_stock, prev_total_cost, prev_average_cost = [0 for i in range(3)]

            if trade.side == 'buy':

                print(prev_stock, trade.amount, prev_total_cost, trade.cost)

                # Close short
                if prev_stock < 0:

                    entry.stock = prev_stock + trade.amount
                    entry.total_cost = entry.stock * prev_average_cost  # decrease
                    entry.average_cost = prev_average_cost

                    # entry.stock = str(entry.stock)
                    # entry.total_cost = str(entry.total_cost)

                    # Determine realized and unrealized profit and loss for USD???-margined contracts
                    # https://www.binance.com/en/support/faq/3a55a23768cb416fb404f06ffedde4b2

                    # Directives
                    exit_price = trade.price
                    mark_price = trade.price
                    entry_price = entry.average_cost

                    realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * (trade.cost * -1)
                    entry.realized_pnl = realized_pnl_base * exit_price
                    entry.unrealized_pnl = trade.amount * -1 * (mark_price - entry_price)

                # Open long
                elif prev_stock >= 0:

                    entry.stock = prev_stock + trade.amount
                    entry.total_cost = prev_total_cost + trade.cost  # increase
                    entry.average_cost = entry.total_cost / entry.stock

                    # No PnL calculation

            elif trade.side == 'sell':

                # Open short
                if prev_stock <= 0:

                    entry.stock = prev_stock - trade.amount  # allow negative stock to distinguish open and close
                    entry.total_cost = prev_total_cost + trade.cost  # increase
                    entry.average_cost = entry.total_cost / abs(entry.stock)

                    # No PnL calculation

                # Close long
                elif prev_stock > 0:

                    entry.stock = prev_stock - trade.amount
                    entry.total_cost = entry.stock * prev_average_cost  # decrease
                    entry.average_cost = prev_average_cost

                    # Determine realized and unrealized profit and loss for USD???-margined contracts
                    # https://www.binance.com/en/support/faq/3a55a23768cb416fb404f06ffedde4b2

                    # Directives
                    exit_price = trade.price
                    mark_price = trade.price
                    entry_price = entry.average_cost

                    realized_pnl_base = ((1 / entry_price) - (1 / exit_price)) * trade.cost
                    entry.realized_pnl = realized_pnl_base * exit_price
                    entry.unrealized_pnl = trade.amount * 1 * (mark_price - entry_price)

            entry.save()

    else:
        log.info('Update contracts inventory no required')
        return

    log.info('Update contracts inventory complete')


@app.task(name='PnL_____Update_inventories')
def update_inventories(pk):
    """
    Update inventories
    """
    chain(update_asset_inventory.si(pk),
          update_contract_inventory.si(pk)
          )()
