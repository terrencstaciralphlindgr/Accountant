from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime
from market.models import Market
import structlog
log = structlog.get_logger(__name__)


def get_market(exchange, tp=None, base=None, quote=None, symbol=None, wallet=None):

    if symbol:
        if wallet:
            obj = Market.objects.get(exchange=exchange, symbol=symbol, wallet=wallet)
        else:
            obj = Market.objects.get(exchange=exchange, symbol=symbol)
        return obj, False

    elif base and quote and (tp or wallet):
        if isinstance(base, str) and isinstance(quote, str):

            try:
                if tp:
                    obj = Market.objects.get(exchange=exchange, type=tp, base__code=base, quote__code=quote)
                elif wallet:
                    obj = Market.objects.get(exchange=exchange, wallet=wallet, base__code=base, quote__code=quote)

            except ObjectDoesNotExist:
                log.info('Market not found, check flipped market')
                try:
                    if tp:
                        obj = Market.objects.get(exchange=exchange, type=tp, base__code=quote, quote__code=base)
                    elif wallet:
                        obj = Market.objects.get(exchange=exchange, wallet=wallet, base__code=quote, quote__code=base)

                except ObjectDoesNotExist:
                    log.info('Market not found')
                else:
                    log.info('Flipped market')
                    return obj, True
            else:
                return obj, False
        else:
            raise Exception('base and quote must be a string')

    else:
        log.error('Unable to select market')


def save_ticker_price(market, response, freq):
    ts = int(datetime.utcnow().timestamp())
    if 'timestamp' in market.ticker:
        if ts > market.ticker['timestamp'] + freq:
            market.ticker = dict(timestamp=ts, last=response['last'])
            market.save()
    else:
        market.ticker = dict(timestamp=ts, last=response['last'])
        market.save()