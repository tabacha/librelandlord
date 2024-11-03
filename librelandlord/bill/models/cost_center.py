from django.db import models
from django.utils.translation import gettext_lazy as _


# CostCenter
# Examples:
# m2 Kalt+Warmwasserzähler der jeweiligen Wohnugen


class CostCenter(models.Model):
    text = models.CharField(max_length=27, verbose_name=_("Cost Center Text"))
    is_oiltank = models.BooleanField(
        verbose_name=_('Is Oiltank')
    )

    def __str__(self):
        return f"{self.text}"
