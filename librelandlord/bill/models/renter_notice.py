from django.db import models
from django.utils.translation import gettext_lazy as _

from .renter import Renter


class RenterNotice(models.Model):
    """
    Hinweise für Mieter in der Jahresabrechnung.

    Ein Hinweis kann für mehrere Mieter gelten und wird in der
    Jahresabrechnung des angegebenen Jahres angezeigt.
    """
    title = models.CharField(
        max_length=100,
        verbose_name=_("Title"),
        help_text=_("Überschrift des Hinweises")
    )
    body = models.TextField(
        verbose_name=_("Body"),
        help_text=_("Inhalt des Hinweises (Markdown erlaubt)")
    )
    billing_year = models.PositiveIntegerField(
        verbose_name=_("Billing Year"),
        help_text=_("Jahr für das dieser Hinweis angezeigt werden soll")
    )
    renters = models.ManyToManyField(
        Renter,
        verbose_name=_("Renters"),
        help_text=_("Mieter für die dieser Hinweis gilt"),
        related_name='notices'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at")
    )

    class Meta:
        verbose_name = _("Renter Notice")
        verbose_name_plural = _("Renter Notices")
        ordering = ['-billing_year', 'title']

    def __str__(self):
        return f"{self.billing_year}: {self.title}"
