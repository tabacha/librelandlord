// Auto-save functionality for meter readings input
document.addEventListener("DOMContentLoaded", function () {
  const autoSaveInputs = document.querySelectorAll(".auto-save");
  let saveTimeout = null;
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

    fetch("/bill/meter_readings_save_single/", {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
      },
    })
      .then((response) => response.json())
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
        // Rotes X bei Netzwerkfehler
        indicator.className = "save-indicator error fas fa-xmark";
        indicator.title = "Netzwerkfehler";
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
      // Warnung prüfen bei jeder Eingabe
      checkWarning(this);

      // Bei Eingabe Indicator wieder anzeigen falls ausgeblendet
      const meterId = this.dataset.meterId;
      const indicator = document.getElementById("indicator-" + meterId);
      if (indicator && this.value.trim()) {
        indicator.style.display = "inline";
        // Spinner sofort anzeigen bei Wertänderung
        indicator.className = "save-indicator saving fas fa-spinner";
        indicator.title = "Wird gespeichert...";
      }

      // Debounce: Warte 3 Sekunden nach der letzten Eingabe
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
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
