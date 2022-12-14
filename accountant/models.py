from django.db import models


class TimestampedModel(models.Model):

    dt_created = models.DateTimeField(null=True, auto_now_add=True)
    dt_modified = models.DateTimeField(null=True, auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-dt_created', '-dt_modified']
