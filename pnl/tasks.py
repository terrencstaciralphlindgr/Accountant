from __future__ import absolute_import, unicode_literals
from _datetime import datetime, timezone
import structlog
from billiard.process import current_process
from django.core.exceptions import ObjectDoesNotExist
from account.models import Account, Trade
from accountant.celery import app
from pnl.models import Inventory

from market.models import Exchange, Market, Currency

log = structlog.get_logger(__name__)


@app.task(bind=True, name='PnL_____Update_asset_inventory')
def update_asset_inventory(self, pk):
    """
    Update inventory
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

    # Select trades and iterate
    trades = Trade.objects.filter(account=account, datetime__gte=start_datetime).order_by('datetime')
    if trades.exists():

        for index, trade in enumerate(trades):

            log.bind(trade=trade.tradeid,
                     amount=trade.amount,
                     side=trade.side)

            log.info('Create inventory entry')
            entry = Inventory.objects.create(account=account,
                                             instrument=0,
                                             datetime=trade.datetime)

            # Determine current stock, total and average costs

            if index > 0:
                prev_trade = trades[index-1]
                prev_stock = prev_trade.stock
                prev_total_cost = prev_trade.total_cost
                prev_average_cost = prev_trade.average_cost

            else:
                prev_stock, prev_total_cost, prev_average_cost = [0 for i in range(3)]

            # Determine new stock, total and average costs

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
