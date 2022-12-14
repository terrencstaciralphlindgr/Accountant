from django.db.models.signals import post_save
from django.dispatch import receiver
from account.models import Balance
from account.tasks import update_inventory
import structlog

log = structlog.get_logger(__name__)


@receiver(post_save, sender=Balance)
def balance_saved(sender, instance, created, raw, using, **kwargs):
    update_inventory(instance.account.pk)
