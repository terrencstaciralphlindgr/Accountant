from django.db.models.signals import post_save
from django.dispatch import receiver
from account.models import Account
import structlog

log = structlog.get_logger(__name__)


@receiver(post_save, sender=Account)
def account_saved(sender, instance, created, raw, using, **kwargs):
    pass
