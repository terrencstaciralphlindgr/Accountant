import uuid
import pytz
from datetime import datetime
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from accountant.models import TimestampedModel
from accountant.methods import datetime_directive_ISO_8601, datetime_directive_ccxt
from market.models import Exchange, Market, Currency
from account.models import Account
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
    instrument = models.IntegerField(choices=Type.choices)
    stock = models.FloatField()
    total_cost = models.FloatField()
    average_cost = models.FloatField()

    class Meta:
        verbose_name_plural = "Inventory"

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        return super(Inventory, self).save(*args, **kwargs)


class AssetPnl(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='asset_pnl', null=True)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='asset_pnl', null=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='asset_pnl', null=True)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='asset_pnl', null=True)
    sale_price = models.FloatField()
    sale_proceeds = models.FloatField()
    realized_pnl = models.FloatField()
    unrealized_pnl = models.FloatField()

    class Meta:
        verbose_name_plural = "Assets Pnl"

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        return super(AssetPnl, self).save(*args, **kwargs)


class ContractPnL(TimestampedModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='contract_pnl', null=True)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='contract_pnl', null=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='contract_pnl', null=True)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='contract_pnl', null=True)
    entry_price = models.FloatField()
    exit_price = models.FloatField()
    realized_pnl = models.FloatField()
    unrealized_pnl = models.FloatField()
    contracts_size = models.FloatField()

    class Meta:
        verbose_name_plural = "Contract PnL"

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        return super(ContractPnL, self).save(*args, **kwargs)