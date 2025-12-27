// Auto-save functionality for meter readings input
document.addEventListener("DOMContentLoaded", function () {
  const autoSaveInputs = document.querySelectorAll(".auto-save");
  let saveTimeouts = {}; // Ein Timer pro Zähler statt einem globalen Timer
  let lastSavedValues = {}; // Speichert letzte gespeicherte Werte

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function saveReading(input) {
    const meterId = input.dataset.meterId;
    const value = input.value.trim();
    const indicator = document.getElementById("indicator-" + meterId);
    const targetDate = document.querySelector(
      'input[name="target_date"]'
    ).value;

    if (!value) return; // Leere Werte nicht speichern

    // Nicht speichern wenn Wert bereits gespeichert wurde
    if (lastSavedValues[meterId] === value) {
      return;
    }

    // Saving Indicator anzeigen (Spinner)
    indicator.className = "save-indicator saving fas fa-spinner";

    // AJAX Request
    const formData = new FormData();
    formData.append("meter_id", meterId);
    formData.append("reading_value", value);
    formData.append("target_date", targetDate);
    formData.append("csrfmiddlewaretoken", getCookie("csrftoken"));

    fetch("/bill/meter-readings-save-single/", {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
      },
    })
      .then((response) => {
        // Prüfe HTTP-Status und erstelle detaillierte Fehlermeldung
        if (!response.ok) {
          let errorMessage = `HTTP ${response.status}`;
          switch (response.status) {
            case 400:
              errorMessage += " - Ungültige Anfrage";
              break;
            case 401:
              errorMessage += " - Nicht autorisiert";
              break;
            case 403:
              errorMessage += " - Zugriff verweigert";
              break;
            case 404:
              errorMessage += " - Seite nicht gefunden";
              break;
            case 405:
              errorMessage += " - Methode nicht erlaubt";
              break;
            case 500:
              errorMessage += " - Interner Serverfehler";
              break;
            case 502:
              errorMessage += " - Bad Gateway";
              break;
            case 503:
              errorMessage += " - Service nicht verfügbar";
              break;
            default:
              errorMessage += ` - ${
                response.statusText || "Unbekannter Fehler"
              }`;
          }
          throw new Error(errorMessage);
        }
        return response.json();
      })
      .then((data) => {
        if (data.success) {
          // Grüner Haken bei Erfolg - bleibt sichtbar
          indicator.className = "save-indicator saved fas fa-check";
          indicator.title = "Erfolgreich gespeichert";

          // Gespeicherten Wert merken
          lastSavedValues[meterId] = value;
        } else {
          // Rotes X bei Fehler
          indicator.className = "save-indicator error fas fa-xmark";
          indicator.title = "Fehler: " + (data.error || "Unbekannter Fehler");
        }
      })
      .catch((error) => {
        // Rotes X bei Netzwerk- oder HTTP-Fehler
        indicator.className = "save-indicator error fas fa-xmark";

        // Detaillierte Fehlermeldung für Mouse-over
        let errorTitle = "Fehler beim Speichern: ";
        if (error.message.startsWith("HTTP")) {
          errorTitle += error.message;
        } else if (
          error.name === "TypeError" &&
          error.message.includes("fetch")
        ) {
          errorTitle += "Verbindungsfehler - Server nicht erreichbar";
        } else {
          errorTitle += error.message || "Unbekannter Netzwerkfehler";
        }

        indicator.title = errorTitle;
        console.error("Auto-save error:", error);
      });
  }

  function checkWarning(input) {
    const meterId = input.dataset.meterId;
    const meterType = input.dataset.meterType;
    const lastReading = input.dataset.lastReading;
    const currentValue = input.value.trim();
    const warningIcon = document.getElementById("warning-" + meterId);

    if (!warningIcon || !lastReading || !currentValue) {
      if (warningIcon) warningIcon.classList.remove("show");
      input.classList.remove("warning");
      // Bei leeren Feldern Indicator ausblenden
      const indicator = document.getElementById("indicator-" + meterId);
      if (indicator && !currentValue) {
        indicator.style.display = "none";
      }
      return;
    }

    // Keine Warnung für Öl-Zähler (OI)
    if (meterType === "OI") {
      warningIcon.classList.remove("show");
      input.classList.remove("warning");
      return;
    }

    // Warnung anzeigen wenn neuer Wert kleiner als letzter Wert
    const lastValue = parseFloat(lastReading);
    const newValue = parseFloat(currentValue);

    if (newValue < lastValue) {
      warningIcon.classList.add("show");
      input.classList.add("warning");
    } else {
      warningIcon.classList.remove("show");
      input.classList.remove("warning");
    }
  }

  // Event Listener für alle Auto-Save Inputs
  autoSaveInputs.forEach((input) => {
    input.addEventListener("input", function () {
      const meterId = this.dataset.meterId;

      // Warnung prüfen bei jeder Eingabe
      checkWarning(this);

      // Bei Eingabe Indicator wieder anzeigen falls ausgeblendet
      const indicator = document.getElementById("indicator-" + meterId);
      if (indicator && this.value.trim()) {
        indicator.style.display = "inline";
        // Spinner sofort anzeigen bei Wertänderung
        indicator.className = "save-indicator saving fas fa-spinner";
        indicator.title = "Wird gespeichert...";
      }

      // Debounce: Warte 3 Sekunden nach der letzten Eingabe
      // Wichtig: Verwende einen spezifischen Timer für diesen Zähler
      if (saveTimeouts[meterId]) {
        clearTimeout(saveTimeouts[meterId]);
      }
      saveTimeouts[meterId] = setTimeout(() => {
        saveReading(this);
      }, 3000);
    });

    input.addEventListener("blur", function () {
      // Nur Warnung prüfen beim Verlassen - kein Speichern
      checkWarning(this);
    });

    // Initial check für bereits eingegebene Werte
    checkWarning(input); // Immer prüfen, auch bei leeren Feldern

    // Bereits geladene Werte als "gespeichert" markieren
    const meterId = input.dataset.meterId;
    if (input.value.trim()) {
      lastSavedValues[meterId] = input.value.trim();
    }
  });
});
