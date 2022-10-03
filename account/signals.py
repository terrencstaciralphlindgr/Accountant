from django.db.models.signals import post_save
from django.dispatch import receiver
from account.models import Account
from account.tasks import fetch_account_balance, fetch_positions
import structlog

log = structlog.get_logger(__name__)


@receiver(post_save, sender=Account)
def account_saved(sender, instance, created, raw, using, **kwargs):

    log.info('Signal received', signal='account saved')

    if created:

        log.info('Fetch account information', account=instance.name)

        fetch_account_balance.delay(instance.id)
        fetch_positions.delay(instance.id)
