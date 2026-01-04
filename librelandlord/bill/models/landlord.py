from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class Landlord(models.Model):
    """
    Singleton-Model für Vermieterdaten.
    Es darf nur genau eine Zeile in dieser Tabelle existieren.
    """
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    property_name = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name=_("Property Name"),
        help_text=_("z.B. Hausverwaltung Haubr.Bahnhofstr.5+7"))
    street = models.CharField(max_length=100, verbose_name=_("Street"))
    postal_code = models.CharField(
        max_length=10, verbose_name=_("Postal Code"))
    city = models.CharField(max_length=50, verbose_name=_("City"))
    phone = models.CharField(max_length=30, blank=True,
                             null=True, verbose_name=_("Phone"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))

    class Meta:
        verbose_name = _("Landlord")
        verbose_name_plural = _("Landlord")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Singleton-Pattern: Es darf nur eine Zeile existieren
        if not self.pk and Landlord.objects.exists():
            raise ValidationError(_("There can only be one Landlord entry."))
        return super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        """
        Gibt die einzige Landlord-Instanz zurück oder None, wenn keine existiert.
        """
        return cls.objects.first()

    def get_sender_line(self):
        """
        Gibt die Absenderzeile für den Briefkopf zurück.
        """
        return f"{self.name} · {self.street} · {self.postal_code} {self.city}"
