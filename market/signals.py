from celery.signals import worker_ready
from market.tasks import ws_loops
import structlog

log = structlog.get_logger(__name__)


@worker_ready.connect
def at_worker_startup(sender, **kwargs):
    log.info('*** Worker startup ***')
    ws_loops.delay()
