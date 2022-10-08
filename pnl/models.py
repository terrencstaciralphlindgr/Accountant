import uuid
from django.db import models
from accountant.models import TimestampedModel
from market.models import Exchange, Currency
from account.models import Account, Trade
import structlog

log = structlog.get_logger(__name__)


class Inventory(TimestampedModel):
    class Type(models.IntegerChoices):
        ASSET = 0, "ASSET"
        CONTRACT = 1, "CONTRACT"

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='inventory', null=True)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='inventory', null=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='inventory', null=True)
    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name='inventory', null=True)
    instrument = models.IntegerField(choices=Type.choices)
    stock = models.FloatField(null=True)
    total_cost = models.FloatField(null=True)
    average_cost = models.FloatField(null=True)
    realized_pnl = models.FloatField(null=True)
    unrealized_pnl = models.FloatField(null=True)
    datetime = models.DateTimeField(null=True)

    class Meta:
        verbose_name_plural = "Inventory"

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        return super(Inventory, self).save(*args, **kwargs)
