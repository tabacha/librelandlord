from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator


def __str__(self):
    return f"{self.date} {self.text} {self.value}"


class AccountPeriod(models.Model):
    text = models.CharField(
        max_length=27, verbose_name=_("Account Period Name"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))

    def __str__(self):
        return f"{self.text} {self.start_date} {self.end_date}"
