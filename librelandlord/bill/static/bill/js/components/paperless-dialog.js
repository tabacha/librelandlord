/**
 * LibreLandlord - Paperless Dialog Component
 *
 * Wiederverwendbares JavaScript für den Paperless-Verknüpfungs-Dialog.
 *
 * Verwendung:
 * 1. Dialog-HTML mit id="paperlessDialogOverlay" einfügen
 * 2. data-paperless-url Attribut mit der Paperless-Base-URL setzen
 * 3. Diese Datei einbinden
 */

(function() {
    'use strict';

    let currentBillId = null;
    let paperlessBaseUrl = '';

    /**
     * Initialisiert den Paperless-Dialog.
     * Liest die Base-URL aus dem data-Attribut des Overlays.
     */
    function init() {
        const overlay = document.getElementById('paperlessDialogOverlay');
        if (!overlay) return;

        paperlessBaseUrl = overlay.dataset.paperlessUrl || '';

        // Event-Listener registrieren
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                closePaperlessDialog();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closePaperlessDialog();
            }
            if (e.key === 'Enter' && overlay.classList.contains('active')) {
                savePaperlessId();
            }
        });
    }

    /**
     * Öffnet den Paperless-Dialog für eine Rechnung.
     */
    function openPaperlessDialog(billId, billText, billDate, billNumber) {
        currentBillId = billId;
        document.getElementById('paperlessDialogBillText').textContent = billText;

        // Suchlinks setzen
        const searchDateLink = document.getElementById('paperlessSearchDate');
        searchDateLink.href = paperlessBaseUrl + '/documents?title_content=' + encodeURIComponent(billDate);
        searchDateLink.textContent = billDate;

        const searchNumberLink = document.getElementById('paperlessSearchNumber');
        searchNumberLink.href = paperlessBaseUrl + '/documents?title_content=' + encodeURIComponent(billNumber);
        searchNumberLink.textContent = billNumber;

        document.getElementById('paperlessIdInput').value = '';
        document.getElementById('paperlessErrorMessage').style.display = 'none';
        document.getElementById('paperlessDialogOverlay').classList.add('active');
        document.getElementById('paperlessIdInput').focus();
    }

    /**
     * Schließt den Paperless-Dialog.
     */
    function closePaperlessDialog() {
        document.getElementById('paperlessDialogOverlay').classList.remove('active');
        currentBillId = null;
    }

    /**
     * Speichert die eingegebene Paperless-ID.
     */
    function savePaperlessId() {
        const paperlessId = document.getElementById('paperlessIdInput').value.trim();
        const errorEl = document.getElementById('paperlessErrorMessage');

        if (!paperlessId) {
            errorEl.textContent = 'Bitte eine Paperless-ID eingeben';
            errorEl.style.display = 'block';
            return;
        }

        if (isNaN(parseInt(paperlessId)) || parseInt(paperlessId) < 1) {
            errorEl.textContent = 'Bitte eine gültige positive Zahl eingeben';
            errorEl.style.display = 'block';
            return;
        }

        // CSRF Token holen
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                         getCookie('csrftoken');

        fetch('/bill/api/bill/' + currentBillId + '/paperless-id/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken
            },
            body: 'paperless_id=' + encodeURIComponent(paperlessId)
        })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                // Seite neu laden um den aktualisierten Button anzuzeigen
                location.reload();
            } else {
                errorEl.textContent = data.error || 'Fehler beim Speichern';
                errorEl.style.display = 'block';
            }
        })
        .catch(function(error) {
            errorEl.textContent = 'Netzwerkfehler: ' + error.message;
            errorEl.style.display = 'block';
        });
    }

    /**
     * Liest einen Cookie-Wert.
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Funktionen global verfügbar machen
    window.openPaperlessDialog = openPaperlessDialog;
    window.closePaperlessDialog = closePaperlessDialog;
    window.savePaperlessId = savePaperlessId;

    // Initialisierung bei DOM-Ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
