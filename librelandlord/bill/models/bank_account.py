from django.db import models
from django.utils.translation import gettext_lazy as _


class BankAccount(models.Model):
    """
    Bankkonto oder Barkasse des Vermieters.

    Ermöglicht Zuordnung von Transaktionen und CSV-Import.
    Unterstützt sowohl echte Bankkonten (mit IBAN) als auch
    Barkassen (ohne IBAN).
    """

    class AccountType(models.TextChoices):
        BANK = 'BANK', _('Bank Account')
        CASH = 'CASH', _('Cash Box (Barkasse)')

    name = models.CharField(
        max_length=100,
        verbose_name=_("Account Name"),
        help_text=_("z.B. 'Mietenkonto', 'Kautionskonto', 'Barkasse'"))

    account_type = models.CharField(
        max_length=4,
        choices=AccountType.choices,
        default=AccountType.BANK,
        verbose_name=_("Account Type"))

    iban = models.CharField(
        max_length=34,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("IBAN"),
        help_text=_("Nur für Bankkonten, nicht für Barkasse"))

    bic = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        verbose_name=_("BIC"))

    bank_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Bank Name"))

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Zusätzliche Informationen zum Konto"))

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        ordering = ['account_type', 'name']

    def __str__(self):
        if self.account_type == self.AccountType.CASH:
            return f"💵 {self.name}"
        return f"{self.name} ({self.iban[-4:] if self.iban else 'N/A'})"

    def save(self, *args, **kwargs):
        if self.iban:
            self.iban = self.iban.replace(' ', '').upper()
        # Barkasse darf keine IBAN haben
        if self.account_type == self.AccountType.CASH:
            self.iban = None
            self.bic = None
            self.bank_name = None
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.account_type == self.AccountType.BANK and not self.iban:
            raise ValidationError({
                'iban': _("Bank accounts require an IBAN.")
            })

    @property
    def is_cash(self) -> bool:
        return self.account_type == self.AccountType.CASH

    @classmethod
    def get_by_iban(cls, iban: str):
        """Findet ein Bankkonto anhand der IBAN."""
        if not iban:
            return None
        iban_clean = iban.replace(' ', '').upper()
        return cls.objects.filter(iban=iban_clean, is_active=True).first()
