from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
import secrets
import string

from .apartment import Apartment


def generate_renter_token():
    """Generiert einen zufälligen 32-Zeichen Token (a-zA-Z0-9)."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

# Define a model representing renters.


class Renter(models.Model):
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, verbose_name=_("Apartment"))
    first_name = models.CharField(max_length=30, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=30, verbose_name=_("Last Name"))
    alt_street = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Alternative Street"))
    postal_code = models.CharField(
        max_length=10, blank=True, null=True, verbose_name=_("Postal Code"))
    city = models.CharField(max_length=30, blank=True,
                            null=True, verbose_name=_("City"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("Phone"))

    # Notfallkontakt
    emergency_contact_name = models.CharField(
        max_length=60, blank=True, null=True, verbose_name=_("Emergency contact name"))
    emergency_contact_relationship = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Relationship to renter"))
    emergency_contact_phone = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Emergency contact phone"))
    emergency_contact_address = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Emergency contact address"))

    # Kaution
    deposit_account = models.CharField(
        max_length=34, blank=True, null=True, verbose_name=_("Deposit account number"))
    deposit_amount = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Deposit amount"))

    # Weitere Kontaktinfos
    additional_contact_info = models.TextField(
        blank=True, null=True, verbose_name=_("Additional contact info"))

    move_in_date = models.DateField(verbose_name=_("Move in on date"))
    move_out_date = models.DateField(
        null=True, blank=True, verbose_name=_("Move out date"))
    contract_start_date = models.DateField(
        null=True, blank=True, verbose_name=_("Contract start date"),
        help_text=_("Start date of the rental contract. Defaults to move-in date if not set."))
    contract_end_date = models.DateField(
        null=True, blank=True, verbose_name=_("Contract end date"),
        help_text=_("End date of the rental contract. Defaults to move-out date if not set."))
    is_owner_occupied = models.BooleanField(
        default=False,
        verbose_name=_("Owner occupied"),
        help_text=_("Check if this unit is occupied by the owner or family members. "
                    "These are not considered rental income for tax purposes."))

    # Token für externen Zugriff auf Dokumente (z.B. Heating Info PDF)
    token = models.CharField(
        max_length=32,
        default=generate_renter_token,
        editable=False,
        verbose_name=_("Access Token"),
        help_text=_("Token for external access to documents without login."))
    token_updated_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name=_("Token updated at"),
        help_text=_("When the access token was last updated."))

    # Opt-out für Heizungsinfo
    wants_heating_info = models.BooleanField(
        default=True,
        verbose_name=_("Wants heating info"),
        help_text=_("Whether the renter wants to receive monthly heating information."))

    def save(self, *args, **kwargs):
        # Setze Vertragsdaten auf Einzugs-/Auszugsdatum wenn nicht explizit gesetzt
        if self.contract_start_date is None:
            self.contract_start_date = self.move_in_date
        if self.contract_end_date is None:
            self.contract_end_date = self.move_out_date
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.apartment}"

    def regenerate_token(self):
        """Generiert einen neuen Token für diesen Mieter."""
        self.token = generate_renter_token()
        self.token_updated_at = timezone.now()
        self.save(update_fields=['token', 'token_updated_at'])
