"""
Email service for LibreLandlord.

Provides functions for sending emails with support for a debug mode
that redirects all emails to a test address.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from datetime import date

from ..models import Renter, HeatingInfo, Landlord

import logging

logger = logging.getLogger(__name__)


def get_recipient_email(email: str) -> str:
    """
    Returns the actual recipient address.

    If EMAIL_DEBUG_RECIPIENT is set, returns that address instead of the original.
    """
    debug_recipient = getattr(settings, 'EMAIL_DEBUG_RECIPIENT', '')
    if debug_recipient:
        logger.info(f"Debug mode: Email to {email} redirected to {debug_recipient}")
        return debug_recipient
    return email


def send_heating_info_email(renter: Renter, heating_infos: list) -> bool:
    """
    Sends an email with the heating info link to a renter.

    Args:
        renter: The renter to send the email to.
        heating_infos: List of HeatingInfo entries to mark as sent on success.

    Returns:
        True on success, False on error.
    """
    if not renter.email:
        logger.warning(f"No email address for renter {renter}.")
        return False

    if not renter.wants_heating_info:
        logger.info(f"Renter {renter} has unsubscribed from heating info.")
        return False

    site_url = getattr(settings, 'SITE_URL', '')
    if not site_url:
        logger.error("SITE_URL not configured.")
        return False

    pdf_url = f"{site_url}/bill/heating_info/token/{renter.token}.pdf"
    json_url = f"{site_url}/bill/heating_info/token/{renter.token}.json"
    unsubscribe_url = f"{site_url}/bill/heating_info/token/{renter.token}/unsubscribe"

    recipient = get_recipient_email(renter.email)
    debug_mode = getattr(settings, 'EMAIL_DEBUG_RECIPIENT', '')

    subject = "Ihre monatliche Heizungsinformation"

    # Show original recipient in debug mode
    debug_info = ""
    if debug_mode:
        debug_info = f"\n\n[DEBUG: Original recipient would be: {renter.email}]"

    landlord = Landlord.get_instance()

    message = render_to_string('heating_info_email.txt', {
        'first_name': renter.first_name,
        'last_name': renter.last_name,
        'pdf_url': pdf_url,
        'json_url': json_url,
        'unsubscribe_url': unsubscribe_url,
        'landlord_name': landlord.name if landlord else "Ihr Vermieter",
        'landlord_street': landlord.street if landlord else "",
        'landlord_postal_code': landlord.postal_code if landlord else "",
        'landlord_city': landlord.city if landlord else "",
        'landlord_phone': landlord.phone if landlord else "",
        'landlord_email': landlord.email if landlord else "",
        'debug_info': debug_info,
    })

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info(f"Heating info email sent to {recipient} (renter: {renter}).")

        # On success: mark all HeatingInfo entries as sent
        for hi in heating_infos:
            hi.sent = True
            hi.save(update_fields=['sent'])

        return True
    except Exception as e:
        logger.error(f"Error sending email to {recipient}: {e}")
        # On error: do NOT modify the sent field
        return False


def send_heating_info_emails() -> dict:
    """
    Sends heating info emails to all renters with new (unsent) HeatingInfo entries.

    Finds all HeatingInfo entries with sent=False, groups them by apartment/renter,
    and sends only one email per renter. On success, all affected HeatingInfo
    entries are marked as sent=True.

    Returns:
        dict with 'sent', 'skipped', 'errors' lists
    """
    today = date.today()
    result = {
        'sent': [],
        'skipped': [],
        'errors': []
    }

    # Find all unsent HeatingInfo entries, grouped by apartment
    unsent_heating_infos = HeatingInfo.objects.filter(
        sent=False
    ).select_related('apartment').order_by('apartment_id', '-year', '-month')

    # Group by apartment
    apartments_with_unsent = {}
    for hi in unsent_heating_infos:
        apt_id = hi.apartment_id
        if apt_id not in apartments_with_unsent:
            apartments_with_unsent[apt_id] = {
                'apartment': hi.apartment,
                'heating_infos': []
            }
        apartments_with_unsent[apt_id]['heating_infos'].append(hi)

    if not apartments_with_unsent:
        logger.info("No unsent HeatingInfo entries found.")
        return result

    # For each apartment, find the active renter and send email
    for apt_id, data in apartments_with_unsent.items():
        apartment = data['apartment']
        heating_infos = data['heating_infos']

        # Find active renter for this apartment
        active_renters = Renter.objects.filter(
            apartment=apartment,
            email__isnull=False,
            wants_heating_info=True
        ).exclude(
            email=''
        )

        # Only renters who haven't moved out yet
        active_renters = [
            r for r in active_renters
            if r.move_out_date is None or r.move_out_date >= today
        ]

        if not active_renters:
            result['skipped'].append({
                'apartment': str(apartment),
                'reason': 'No active renter with email found'
            })
            continue

        # Take the first active renter (usually there's only one)
        renter = active_renters[0]

        success = send_heating_info_email(renter, heating_infos)
        if success:
            result['sent'].append({
                'renter': str(renter),
                'apartment': str(apartment),
                'heating_info_count': len(heating_infos)
            })
        else:
            result['errors'].append({
                'renter': str(renter),
                'apartment': str(apartment),
                'reason': 'Email sending failed'
            })

    logger.info(
        f"Heating info emails sent: {len(result['sent'])} sent, "
        f"{len(result['skipped'])} skipped, {len(result['errors'])} errors"
    )

    return result
