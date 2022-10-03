import random
from datetime import datetime, timezone
import ccxt
import pandas as pd
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from accountant.models import TimestampedModel
from market.models import Market, Exchange, Currency
from market.methods import get_market
import structlog

log = structlog.get_logger(__name__)


class Account(TimestampedModel):
    class PriceSource(models.IntegerChoices):
        LAST = 0, "LAST"
        OPEN = 1, "OPEN"

    class TradingMode(models.IntegerChoices):
        HYBRID = 0, "HYBRID"
        FUTURE = 1, "FUTURE"

    name = models.CharField(max_length=20)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='account', null=True)
    quote = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='account_quote', null=True)
    production = models.BooleanField(default=False, null=True, blank=True)
    limit_price_tolerance = models.DecimalField(default=0, max_digits=4, decimal_places=3)
    api_key, api_secret = [models.CharField(max_length=100, blank=True) for i in range(2)]
    password = models.CharField(max_length=100, null=True, blank=True)
    price_source = models.IntegerField(choices=PriceSource.choices, default=PriceSource.LAST)
    trading_mode = models.IntegerField(choices=TradingMode.choices, default=TradingMode.HYBRID)
    leverage = models.DecimalField(default=1, max_digits=2, decimal_places=1, validators=[
        MaxValueValidator(2),
        MinValueValidator(1)])
    collateral_ratio = models.DecimalField(default=1, max_digits=2, decimal_places=0, validators=[
        MaxValueValidator(20),
        MinValueValidator(1)])
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

    def get_position_risk(self):

        log.info('Set position risk')

        client = self.exchange.get_ccxt_client(self)
        instrumentid = Market.objects.get(exchange=self.exchange,
                                          wallet='future',
                                          base=self.strategy.base,
                                          quote=self.quote
                                          ).instrument

        pos_risk = client.fapiPrivate_get_positionrisk()
        self.position_risk = dict()
        self.position_risk = [i for i in pos_risk if i['symbol'] == instrumentid][0]
        self.collateral_ratio = int(self.position_risk['leverage'])
        self.save()

    def set_leverage(self, leverage):
        client = self.exchange.get_ccxt_client(self)
        instrumentid = Market.objects.get(exchange=self.exchange,
                                          wallet='future',
                                          base=self.strategy.base,
                                          quote=self.quote
                                          ).instrument
        response = client.fapiPrivate_post_leverage({"symbol": instrumentid, "leverage": leverage, })
        self.collateral_ratio = response['leverage']
        self.get_position_risk()
        self.save()

    def assets_df(self, wallet=None, free=False, used=False):
        """
        Returns a dataframe with assets
        """
        from trading.models import Asset
        self.refresh_from_db()
        qs = Asset.objects.filter(account=self).all()
        fields = ['currency__code', 'total', 'total_value']

        if wallet:
            qs = qs.filter(wallet=wallet)
            fields.append('wallet')

        if free:
            fields += ['free', 'free_value']

        if used:
            fields += ['used', 'used_value']

        df = pd.DataFrame(list(qs.values(*fields)))
        if not df.empty:

            df.columns = df.columns.str.replace('currency__code', 'code')

            df['type'] = 'asset'
            df['side'] = 'long'

            idx = ['code', 'type']
            if wallet:
                idx.insert(0, 'wallet')
            df.set_index(idx, inplace=True)

        return df

    def positions_df(self):
        from trading.models import Position
        self.refresh_from_db()
        df = pd.DataFrame(list(Position.objects.filter(account=self).all().values('market__base__code',
                                                                                  'contracts',
                                                                                  'notional',
                                                                                  'side')))
        if not df.empty:
            df.columns = ['code', 'total', 'total_value', 'side']
            df['type'] = 'perpetual'

            idx = ['code', 'type']
            if self.exchange.get_wallets():
                df['wallet'] = 'future'
                idx.insert(0, 'wallet')

            df.set_index(idx, inplace=True)

            if df['side'][0] == 'short':
                df['total_value'] = -df['total_value']
                df['total'] = -df['total']

        return df

    def orders_df(self):

        from trading.models import Order
        orders = Order.objects.filter(account=self, status__in=['open', 'preparation']).all()
        df = pd.DataFrame()

        if orders.exists():

            for order in orders:
                order.refresh_from_db()

                # Determine quantity
                if order.status == 'preparation':
                    amount = order.amount
                elif order.status == 'open':
                    amount = order.remaining
                elif order.status == 'cancel':
                    log.info('Order has been canceled')
                    continue

                # Order value
                value = amount * order.price

                if order.side == 'sell':
                    amount = -amount
                    value = -value

                log.info('Found order {0}: {1} {2} {3} ({4})'.format(order.clientid,
                                                                     order.side,
                                                                     abs(amount),
                                                                     order.market.base.code,
                                                                     order.status
                                                                     ))
                # Build index
                levels = [order.market.base.code, 'order']
                if self.exchange.get_wallets():
                    levels.insert(0, order.market.wallet)
                idx = pd.MultiIndex.from_tuples([tuple(levels)])

                # Create dataframe
                tmp = pd.DataFrame(data={'total': [amount],
                                         'total_value': [value],
                                         'market': [order.market.type]
                                         }, index=idx)
                tmp['side'] = order.side
                df = pd.concat([tmp, df])

            return df
        else:
            # log.info('No open order found')
            return df

    def total_value(self, code=None, wallet=None):
        """
        Returns total value of an account
        """
        df = self.assets_df(wallet)

        if wallet:
            df = df.droplevel(0)

        if code:
            if code in df.index:
                return df.groupby(level=[0]).sum().loc[code].total_value
            else:
                return 0
        else:
            return df.groupby(level=[1]).sum().loc['asset'].total_value

    @property
    def total_assets_value(self):
        return self.total_value()

    def free_quantity(self, code, wallet=None):
        df = self.assets_df(free=True, wallet=wallet)

        if wallet:
            df = df.loc[wallet]

        if code in df.index:
            return df.loc[(code, 'asset')].free
        else:
            return 0

    @property
    def has_order(self):
        return True if not self.orders_df().empty else False

    @property
    def has_order_perp(self):
        orders = self.orders_df()
        if not orders.empty:
            return True if 'perpetual' in orders.market.values else False

    @property
    def has_order_spot(self):
        orders = self.orders_df()
        if not orders.empty:
            return True if 'spot' in orders.market.values else False

    @property
    def has_position(self):
        from trading.models import Position
        if Position.objects.filter(account=self).exists():
            return True

    @property
    def has_position_short(self):
        from trading.models import Position
        if Position.objects.filter(account=self, side='short').exists():
            return True

    @property
    def has_position_long(self):
        from trading.models import Position
        if Position.objects.filter(account=self, side='long').exists():
            return True

    @property
    def base_price(self):

        # Last price
        if self.price_source == 0:

            # Select spot market
            market = get_market(self.exchange,
                                base=self.strategy.base.code,
                                quote=self.quote.code,
                                tp='spot')[0]

            # Select price in dictionary
            if 'last' in market.ticker:
                if 'timestamp' in market.ticker:
                    ts = int(datetime.now(timezone.utc).timestamp())
                    if ts < market.ticker['timestamp'] + 60:
                        return market.ticker['last']
                    else:
                        raise Exception("Last price is not updated")
            else:
                raise Exception("Last price not available")

        # Open price
        elif self.price_source == 1:
            return self.strategy.base.get_open_price(self.exchange, self.quote.code)

    def target(self):
        df = pd.DataFrame(data=[self.strategy.get_weight()],
                          index=[self.strategy.base.code],
                          columns=['weight']
                          )

        # Determine target value
        df['value'] = df['weight'] * self.total_value() * float(self.leverage)

        # Determine target quantity
        df['quantity'] = df['value'] / self.base_price

        return df

    def exposure(self):

        if self.exchange.get_wallets():
            spot = self.assets_df(wallet='spot')
            futu = self.assets_df(wallet='future')
            assets = pd.concat([spot, futu], axis=0, sort=True)

        else:
            assets = self.assets_df()

        df = pd.concat([assets,
                        self.positions_df(),
                        self.orders_df()
                        ], axis=0, sort=True)

        # Drop quote asset from rows
        # and sum rows by codes and types
        if self.exchange.get_wallets():
            df = df.loc[df.index.get_level_values(1) != self.quote.code]
            df = df.groupby(level=[0, 1, 2]).sum()
        else:
            df = df.loc[df.index.get_level_values(0) != self.quote.code]
            df = df.groupby(level=[0, 1]).sum()

        for i, j in assets.iterrows():
            log.info(str(i) + ' ' + str(round(j['total_value'], 1)))

        return df

    def delta(self):
        if self.exchange.get_wallets():
            return self.delta_1()
        else:
            return self.delta_2()

    def delta_1(self):

        def short():

            if not self.has_order_perp:

                # Determine the required margin for the trade
                trade_abs_value = abs(desired_pos_value) - abs(position_open_value)  # positive
                margin_req = (trade_abs_value / int(self.collateral_ratio))
                margin_order = min(margin_req, position_margin_free)  # Limit margin to available margin

                df.loc[('future', base, 'perpetual'), 'action'] = 'open_short'
                df.loc[('future', base, 'perpetual'), 'delta'] = margin_order * int(self.collateral_ratio) / price

                # Transfer available cash from spot to future account
                if free_spot_cash_quantity:
                    log.info('Move available cash from spot')
                    log.info('Transfer {0} {1} from spot'.format(round(free_spot_cash_quantity, 1), quote))

                    df.loc[('future', self.quote.code, 'perpetual'), 'action'] = 'transfer_in'
                    df.loc[('future', self.quote.code, 'perpetual'), 'delta'] = free_spot_cash_quantity

            else:
                log.info('An order is already open in future')

        base = self.strategy.base.code
        quote = self.quote.code
        price = self.base_price

        # Exposition target
        df = self.exposure()
        total_exposure = df['total_value'].sum()
        target_value = self.target()['value'][0]

        # Determine maximum spot value, position size and margin
        account_value = self.total_value()
        position_long_value_max = account_value * (float(self.leverage) - 1)
        position_long_margin_max = position_long_value_max / int(self.collateral_ratio)
        account_value_spot_limit = account_value - position_long_margin_max

        position_short_value_max = -(account_value * float(self.leverage))
        position_short_margin_max = account_value

        # Determine wallets quantities n values
        account_value_futu_quote = self.total_value(wallet='future')
        account_value_spot_base = self.total_value(wallet='spot', code=base)
        free_spot_base_quantity = self.free_quantity(base, wallet='spot')
        free_spot_cash_quantity = self.free_quantity(quote, wallet='spot')

        # Determine position sizes and free margin
        pos = self.positions_df()
        position_open_quantity = pos.loc[('future', base, 'perpetual')].total if self.has_position else 0
        position_open_value = pos.loc[('future', base, 'perpetual')].total_value if self.has_position else 0
        position_margin_used = abs(position_open_value) / int(self.collateral_ratio)
        position_margin_free = max(0, account_value_futu_quote - position_margin_used)

        log.info('')
        for metric in [('Exposure                    ', 'total_exposure'),
                       ('Target value                ', 'target_value'),
                       ('Account value               ', 'account_value'),
                       ('Account value spot    (BTC) ', 'account_value_spot_base'),
                       ('Account limit spot    (BTC) ', 'account_value_spot_limit'),
                       ('Account value spot    (BUSD)', 'free_spot_cash_quantity'),
                       ('Account value fut     (BUSD)', 'account_value_futu_quote'),
                       ('Position long value   (max) ', 'position_long_value_max'),
                       ('Position long margin  (max) ', 'position_long_margin_max'),
                       ('Position short value  (max) ', 'position_short_value_max'),
                       ('Position short margin (max) ', 'position_short_margin_max'),
                       ('Position margin used        ', 'position_margin_used'),
                       ('Position margin free        ', 'position_margin_free'),
                       ('Position size               ', 'position_open_quantity'),
                       ('Position value              ', 'position_open_value')
                       ]:
            log.info('{0} {1}'.format(metric[0], round(eval(metric[1]), 4)))
        log.info('')

        # Long
        if target_value > 0:

            # If a short is open then close the position first
            if self.has_position_short:

                log.info('Close short position')

                if not self.has_order_perp:

                    df.loc[('future', base), 'action'] = 'close_short'
                    df.loc[('future', base), 'delta'] = position_open_value / price

                else:
                    log.info('An order is already open in future')

            # Increase our exposure ?
            if target_value > total_exposure:

                # Limit is not reached yet ?
                if account_value_spot_base < account_value_spot_limit * 0.95:

                    log.info('Trade in spot until limit is reached')

                    if not self.has_order_spot:

                        desired_value = target_value - total_exposure
                        account_capacity = account_value_spot_limit - account_value_spot_base
                        buy_value = min(desired_value, account_capacity, free_spot_cash_quantity)
                        df.loc[('spot', base), 'action'] = 'buy_spot'
                        df.loc[('spot', base), 'delta'] = -buy_value / price

                        if buy_value < desired_value:

                            log.info('Cash is insufficient, limit trade amount')

                            # Determine transfer value
                            tx = min(desired_value - buy_value, position_margin_free)
                            if tx:

                                log.info('Transfer {0} {1} from future'.format(round(tx, 1), quote))

                                position_margin_free -= tx  # update free margin
                                df.loc[('spot', self.quote), 'action'] = 'transfer_in'
                                df.loc[('spot', self.quote), 'delta'] = tx

                            else:

                                log.warning('No margin available in future')

                    else:
                        log.info('An order is already open in spot')

                else:

                    if account_value_spot_base > account_value_spot_limit:

                        log.warning('Spot account overload')

                        if not self.has_order_spot:
                            log.warning('Sell spot to make margin resource available')

                            # Determine trade value
                            trade_value = (account_value_spot_base - account_value_spot_limit) * 1.05
                            df.loc[('spot', base), 'action'] = 'sell_spot'
                            df.loc[('spot', base), 'delta'] = trade_value / price

                        else:
                            log.info('An order is already open in spot')

                    else:

                        if not self.has_position_short:

                            log.info("Spot account as reached it's capacity")

                            # Spot account is at capacity, open or upgrade a long position.
                            # Calculate trade value and determine margin requirement.
                            trade_value = target_value - total_exposure
                            margin_req = trade_value / int(self.collateral_ratio)

                            if not self.has_order_perp:

                                log.info('Open or upgrade a long position')

                                if position_margin_free:

                                    # Determine margin to reserve for the order
                                    margin_order = min(margin_req, position_margin_free)
                                    if margin_order < margin_req:

                                        log.warning('Margin is insufficient'.format(
                                            round(margin_order / margin_req, 4) * 100))

                                        # Determine extra margin needed
                                        margin_miss = margin_req - margin_order

                                        # Determine transfer
                                        if free_spot_cash_quantity:

                                            tx = min(margin_miss, free_spot_cash_quantity)
                                            margin_order += tx

                                            log.info('Transfer {0} {1} from spot'.format(round(tx, 1), quote))

                                            df.loc[('future', self.quote.code), 'action'] = 'transfer_in'
                                            df.loc[('future', self.quote.code), 'delta'] = tx

                                        else:
                                            log.warning('No cash left in spot')

                                    df.loc[('future', base), 'action'] = 'open_long'
                                    df.loc[('future', base), 'delta'] = -(
                                            margin_order * int(self.collateral_ratio)) / price

                                else:
                                    log.info('No margin available')

                                    # Determine transfer
                                    if free_spot_cash_quantity:

                                        tx = min(margin_req, free_spot_cash_quantity)
                                        df.loc[('future', base), 'action'] = 'open_long'
                                        df.loc[('future', base), 'delta'] = -(tx * int(self.collateral_ratio)) / price

                                        log.info('Transfer {0} {1} from spot'.format(round(tx, 1), quote))

                                        df.loc[('future', self.quote.code), 'action'] = 'transfer_in'
                                        df.loc[('future', self.quote.code), 'delta'] = tx

                                    else:
                                        log.warning('No cash left in spot')
                            else:
                                log.info('An order is already open in future')
            else:

                # So we need to decrease our exposure...
                # Determine the downgrade value to match new target
                downgrade_value = total_exposure - target_value

                # Decrease a long position
                if self.has_position_long and not self.has_position_short:

                    log.info('Downgrade a long position')

                    if not self.has_order_perp:

                        # Limit trade value to position size
                        trade_value = min(downgrade_value, position_open_value)
                        df.loc[('future', base), 'action'] = 'close_long'
                        df.loc[('future', base), 'delta'] = trade_value / price

                    else:
                        log.info('An order is already open in future')

                else:

                    log.info('Sell spot to reach our new target')

                    if not self.has_order_spot:

                        # If there is no position to close, then sell spot
                        # Limit trade value to asset in spot
                        trade_qty = min(downgrade_value / price, free_spot_base_quantity)
                        df.loc[('spot', base), 'action'] = 'sell_spot'
                        df.loc[('spot', base), 'delta'] = trade_qty

                    else:
                        log.info('An order is already open in spot')

        # Short
        else:

            # Close long position
            if self.has_position_long:

                log.info('Close long position')

                if not self.has_order_perp:

                    df.loc[('future', base), 'action'] = 'close_long'
                    df.loc[('future', base), 'delta'] = position_open_value / price

                else:
                    log.info('An order is already open in future')

            else:

                log.info('No long position left')

                # Determine desired notional value and margin
                desired_pos_value = target_value

                if self.has_position_short:

                    # Close short in excess ?
                    if position_open_value < desired_pos_value:

                        log.info('Reduce short position')

                        if not self.has_order_perp:

                            df.loc[('future', base), 'action'] = 'close_short'
                            df.loc[('future', base), 'delta'] = (position_open_value - desired_pos_value) / price

                        else:
                            log.info('An order is already open in future')

                    else:
                        log.info('Increase short position')
                        short()

                else:
                    log.info('Open new short position')
                    short()

            # Sell spot
            if account_value_spot_base:

                log.info('Sell base asset'.format(base))

                if not self.has_order_spot:

                    trade_qty = min(account_value_spot_base / price, free_spot_base_quantity)
                    df.loc[('spot', base), 'action'] = 'sell_spot'
                    df.loc[('spot', base), 'delta'] = trade_qty

                else:
                    log.info('An order is already open in spot')

        return df.droplevel(0)

    def delta_2(self):

        def short():

            if not self.has_order_perp:

                # Determine the required margin for the trade
                trade_abs_value = abs(desired_pos_value) - abs(position_open_value)  # positive
                margin_req = (trade_abs_value / int(self.collateral_ratio))
                margin_order = min(margin_req, position_margin_free)  # Limit margin to available margin

                df.loc[(base, 'perpetual'), 'action'] = 'open_short'
                df.loc[(base, 'perpetual'), 'delta'] = margin_order * int(self.collateral_ratio) / price

            else:
                log.info('An order is already open in future')

        base = self.strategy.base.code
        quote = self.quote.code
        price = self.base_price

        # Exposition target
        df = self.exposure()
        if base in df.index.get_level_values(0):
            total_exposure = df.loc[base].total_value.sum()
        else:
            total_exposure = 0

        target_value = self.target()['value'][0]

        # Determine maximum spot value, position size and margin
        account_value = self.total_value()
        position_long_value_max = account_value * (float(self.leverage) - 1)
        position_long_margin_max = position_long_value_max / int(self.collateral_ratio)
        total_value_base_limit = account_value - position_long_margin_max

        if self.trading_mode == 1:
            total_value_base_limit = 0

        position_short_value_max = -(account_value * float(self.leverage))
        position_short_margin_max = account_value

        # Create variables to limit db access
        total_value_quote = max(0, self.total_value(code=quote))
        total_value_base = self.total_value(code=base)
        free_quantity_base = self.free_quantity(base)
        free_quantity_quote = self.free_quantity(quote)

        # Determine position sizes and free margin
        pos = self.positions_df()
        position_open_quantity = pos.loc[(base, 'perpetual')].total if self.has_position else 0
        position_open_value = pos.loc[(base, 'perpetual')].total_value if self.has_position else 0
        position_margin_used = abs(position_open_value) / int(self.collateral_ratio)
        position_margin_free = max(0, total_value_quote - position_margin_used)

        log.info('')
        for metric in [('Exposure                    ', 'total_exposure'),
                       ('Target value                ', 'target_value'),
                       ('Account value               ', 'account_value'),
                       ('Account value base          ', 'total_value_base'),
                       ('Account value quote         ', 'total_value_quote'),
                       ('Account limit base          ', 'total_value_base_limit'),
                       ('Position long value   (max) ', 'position_long_value_max'),
                       ('Position long margin  (max) ', 'position_long_margin_max'),
                       ('Position short value  (max) ', 'position_short_value_max'),
                       ('Position short margin (max) ', 'position_short_margin_max'),
                       ('Position margin used        ', 'position_margin_used'),
                       ('Position margin free        ', 'position_margin_free'),
                       ('Position size               ', 'position_open_quantity'),
                       ('Position value              ', 'position_open_value')
                       ]:
            log.info('{0} {1}'.format(metric[0], round(eval(metric[1]), 2)))
        log.info('')

        # Long
        if target_value > 0:

            # If a short is open then close the position first
            if self.has_position_short:

                log.info('Close short position')
                if not self.has_order_perp:

                    df.loc[(base, 'perpetual'), 'action'] = 'close_short'
                    df.loc[(base, 'perpetual'), 'delta'] = position_open_value / price

                else:
                    log.info('An order is already open in future')

            # Increase our exposure ?
            if target_value > total_exposure:

                # Limit is not reached yet ?
                if total_value_base < total_value_base_limit * 0.95 \
                        and self.trading_mode == 0:

                    log.info('Trade in spot until limit is reached')

                    if not self.has_order_spot:

                        desired_value = target_value - total_exposure
                        account_capacity = total_value_base_limit - total_value_base
                        buy_value = min(desired_value, account_capacity, free_quantity_quote)
                        df.loc[(base, 'asset'), 'action'] = 'buy_spot'
                        df.loc[(base, 'asset'), 'delta'] = -buy_value / price

                        if buy_value < desired_value:
                            log.info('Cash is insufficient, limit trade amount')

                    else:
                        log.info('An order is already open in spot')

                else:

                    if total_value_base > total_value_base_limit \
                            and self.trading_mode == 0:

                        log.warning('Spot account overload')

                        if not self.has_order_spot:
                            log.warning('Sell spot to make margin resource available')

                            # Determine trade value
                            trade_value = (total_value_base - total_value_base_limit) * 1.05
                            df.loc[(base, 'asset'), 'action'] = 'sell_spot'
                            df.loc[(base, 'asset'), 'delta'] = trade_value / price

                        else:
                            log.info('An order is already open in spot')

                    else:

                        if not self.has_position_short:

                            if self.trading_mode == 0:
                                log.info("Spot account as reached it's capacity")

                            # Spot account is at capacity, open or upgrade a long position.
                            # Calculate trade value and determine margin requirement.
                            trade_value = target_value - total_exposure
                            margin_req = trade_value / int(self.collateral_ratio)

                            if not self.has_order_perp:

                                log.info('Open or upgrade a long position')
                                if position_margin_free:

                                    # Determine margin to reserve for the order
                                    margin_order = min(margin_req, position_margin_free)

                                    if margin_order < margin_req:
                                        log.warning('Margin is insufficient'.format(
                                            round(margin_order / margin_req, 4) * 100))

                                    df.loc[(base, 'perpetual'), 'action'] = 'open_long'
                                    df.loc[(base, 'perpetual'), 'delta'] = -(
                                            margin_order * int(self.collateral_ratio)) / price

                                else:
                                    log.info('No margin available')

                                    if not free_quantity_quote:
                                        log.warning('No cash left in account')
                            else:
                                log.info('An order is already open in future')
            else:

                # So we need to decrease our exposure...
                # Determine the downgrade value to match new target
                downgrade_value = total_exposure - target_value

                # Decrease a long position
                if self.has_position_long and not self.has_position_short:

                    log.info('Downgrade a long position')
                    if not self.has_order_perp:

                        # Limit trade value to position size
                        trade_value = min(downgrade_value, position_open_value)
                        df.loc[(base, 'perpetual'), 'action'] = 'close_long'
                        df.loc[(base, 'perpetual'), 'delta'] = trade_value / price

                    else:
                        log.info('An order is already open in future')

                else:

                    if self.trading_mode == 0:

                        log.info('Sell spot to reach our new target')
                        if not self.has_order_spot:

                            # If there is no position to close, then sell spot
                            # Limit trade value to asset in spot
                            trade_qty = min(downgrade_value / price, free_quantity_base)
                            df.loc[(base, 'asset'), 'action'] = 'sell_spot'
                            df.loc[(base, 'asset'), 'delta'] = trade_qty

                        else:
                            log.info('An order is already open in spot')

        # Short
        else:

            # Close long position
            if self.has_position_long:

                log.info('Close long position')

                if not self.has_order_perp:

                    df.loc[(base, 'perpetual'), 'action'] = 'close_long'
                    df.loc[(base, 'perpetual'), 'delta'] = position_open_value / price

                else:
                    log.info('An order is already open in future')

            else:

                log.info('No long position left')

                # Determine desired notional value and margin
                desired_pos_value = target_value

                if self.has_position_short:

                    # Close short in excess ?
                    if position_open_value < desired_pos_value:

                        log.info('Reduce short position')

                        if not self.has_order_perp:

                            df.loc[(base, 'perpetual'), 'action'] = 'close_short'
                            df.loc[(base, 'perpetual'), 'delta'] = (position_open_value - desired_pos_value) / price

                        else:
                            log.info('An order is already open in future')

                    else:
                        log.info('Increase short position')
                        short()

                else:
                    log.info('Open new short position')
                    short()

            # Sell spot
            if total_value_base and self.trading_mode == 0:

                log.info('Sell base asset'.format(base))

                if not self.has_order_spot:

                    trade_qty = min(total_value_base / price, free_quantity_base)
                    df.loc[('spot', base), 'action'] = 'sell_spot'
                    df.loc[('spot', base), 'delta'] = trade_qty

                else:
                    log.info('An order is already open in spot')

        return df

    def validate_order(self, idx, action, qty, order_type='limit'):
        """
        Format decimal and validate order quantity.
        Returns a dictionary with order information.
        """
        from trading.methods import limit_amount, limit_cost
        log.bind(account=self.name)

        code, tp = idx
        tp = 'spot' if tp == 'asset' else 'perpetual'
        market, flip = get_market(self.exchange, tp=tp, base=code, quote=self.quote.code)
        side = 'buy' if action in ['close_short', 'open_long', 'buy_spot'] else 'sell'
        close = True if action in ['close_short', 'close_long'] else False
        rounding = self.exchange.rounding_mode_spot if tp == 'spot' else self.exchange.rounding_mode_future

        if market:

            amount = float(ccxt.decimal_to_precision(abs(qty),
                                                     rounding_mode=int(rounding),
                                                     precision=market.precision['amount'],
                                                     counting_mode=self.exchange.get_ccxt_client().precisionMode,
                                                     padding_mode=int(self.exchange.padding_mode)
                                                     ))

            if amount:

                # Test amount limits MIN and MAX
                if limit_amount(market, amount) or close:

                    # Test cost limits MIN and MAX
                    price = self.base_price
                    cost = amount * price
                    min_notional = limit_cost(market, cost)

                    order = dict(
                        action=action,
                        market=market,
                        side=side,
                        amount=amount,
                        price=price,
                        order_type=order_type,
                        params=dict()
                    )

                    # If cost not satisfied and close short set reduce_only = True
                    if not min_notional:
                        if market.exchange.exid == 'binance':
                            if market.type == 'perpetual':
                                if action in ['close_short', 'close_long']:

                                    log.info('Set reduceOnly=True')
                                    order['params'] = dict(reduceOnly=True)
                                    return order

                                else:
                                    log.info("Can't {0} {1} dust".format(action, market.base.code))
                            else:
                                log.info("Can't {0} {1} dust".format(action, market.base.code))
                        else:
                            log.info("Can't {0} {1} dust".format(action, market.base.code))
                    else:
                        return order
                else:
                    log.info('Limit not satisfied ({0} {1})'.format(amount, code))
            else:
                log.info('Amount not satisfied ({0} {1})'.format(amount, code))
        else:
            raise Exception('Market {0}/{1} not found ({2})'.format(code, self.quote.code, tp))

    def create_object(self, order):
        """
        Create Order object with order specs before placing an order to the market
        """
        log.bind(account=self.name)
        alphanumeric = 'abcdefghijklmnopqrstuvwABCDEFGHIJKLMNOPQRSTUVWWXYZ01234689'
        clientid = ''.join((random.choice(alphanumeric)) for x in range(5))
        # clientid = 'boter_' + clientid

        try:

            # Unpack order
            action, market, side, amount, price, order_type, params = order.values()

            # Determine order cost
            cost = price * amount if price else None

            obj = Order.objects.create(
                account=self,
                market=market,
                clientid=clientid,
                type=order_type,
                side=side,
                action=action,
                amount=amount,
                price=price,
                cost=cost,
                params=params,
                status='preparation'
            )

        except Exception as e:
            raise Exception(str(e))

        else:
            log.info('New order object {0} created'.format(clientid))
            return obj.clientid

    def has_recent_trade(self, sec=2):

        from trading.models import Trade
        qs = Trade.objects.filter(order__account=self)
        if qs:
            dt = qs.last().dt_modified
            ts_trade = int(dt.timestamp())
            ts_now = int(datetime.now(timezone.utc).timestamp())
            if ts_now < (ts_trade + sec):
                return True
            else:
                return False
        else:
            return False
