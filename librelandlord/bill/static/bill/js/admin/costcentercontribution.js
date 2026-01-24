(function() {
    'use strict';

    /**
     * Blendet das consumption_calc Feld basierend auf dem distribution_type 
     * des ausgewählten CostCenters ein oder aus.
     * 
     * Funktioniert sowohl:
     * - Im CostCenterContribution Admin (cost_center ist Autocomplete)
     * - Im CostCenter Admin Inline (distribution_type ist Select auf derselben Seite)
     */
    
    // ===== Für CostCenterContribution Admin (eigenständige Seite) =====
    
    function getConsumptionCalcRow() {
        return document.querySelector('.form-row.field-consumption_calc') ||
               document.querySelector('.field-consumption_calc');
    }

    function setRowVisibility(show) {
        var row = getConsumptionCalcRow();
        if (row) {
            row.style.display = show ? '' : 'none';
        }
    }

    function fetchDistributionTypeAndUpdate(costCenterId) {
        if (!costCenterId) {
            setRowVisibility(false);
            return;
        }

        fetch('/bill/api/costcenter/' + costCenterId + '/distribution-type/')
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                if (data.success) {
                    setRowVisibility(data.show_consumption_calc);
                } else {
                    setRowVisibility(true);
                }
            })
            .catch(function(error) {
                console.log('Error fetching distribution type:', error);
                setRowVisibility(true);
            });
    }

    function getCostCenterValue() {
        var hiddenInput = document.getElementById('id_cost_center');
        if (hiddenInput) {
            return hiddenInput.value;
        }
        return null;
    }

    function setupCostCenterContributionAdmin() {
        var costCenterInput = document.getElementById('id_cost_center');
        
        if (!costCenterInput) {
            return;
        }

        var initialValue = getCostCenterValue();
        if (initialValue) {
            fetchDistributionTypeAndUpdate(initialValue);
        } else {
            setRowVisibility(false);
        }

        costCenterInput.addEventListener('change', function() {
            fetchDistributionTypeAndUpdate(this.value);
        });

        // MutationObserver für Autocomplete-Änderungen
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                    fetchDistributionTypeAndUpdate(costCenterInput.value);
                }
            });
        });

        observer.observe(costCenterInput, {
            attributes: true,
            attributeFilter: ['value']
        });

        // Polling als Fallback für Autocomplete
        var lastValue = initialValue;
        setInterval(function() {
            var currentValue = getCostCenterValue();
            if (currentValue !== lastValue) {
                lastValue = currentValue;
                fetchDistributionTypeAndUpdate(currentValue);
            }
        }, 500);
    }

    // ===== Für CostCenter Admin mit Inline =====
    
    function updateInlineConsumptionCalcVisibility(show) {
        // Finde das Inline-Fieldset
        var inlineGroup = document.getElementById('costcentercontribution_set-group');
        if (!inlineGroup) {
            // Fallback: Suche nach beliebigem Element mit costcentercontribution
            inlineGroup = document.querySelector('[id*="costcentercontribution"]');
        }
        
        if (!inlineGroup) {
            return;
        }

        // Für TabularInline: Finde den Header und die Spalten-Index
        var table = inlineGroup.querySelector('table');
        if (table) {
            var headerRow = table.querySelector('thead tr');
            if (headerRow) {
                var headers = headerRow.querySelectorAll('th');
                var consumptionIndex = -1;
                
                // Finde die Spalte mit "Consumption" im Text
                for (var i = 0; i < headers.length; i++) {
                    var headerText = headers[i].textContent.toLowerCase();
                    if (headerText.indexOf('consumption') !== -1 || 
                        headerText.indexOf('verbrauch') !== -1) {
                        consumptionIndex = i;
                        headers[i].style.display = show ? '' : 'none';
                        break;
                    }
                }

                // Alle Zeilen durchgehen und die entsprechende Zelle ausblenden
                if (consumptionIndex >= 0) {
                    var bodyRows = table.querySelectorAll('tbody tr');
                    for (var j = 0; j < bodyRows.length; j++) {
                        var cells = bodyRows[j].querySelectorAll('td');
                        if (cells[consumptionIndex]) {
                            cells[consumptionIndex].style.display = show ? '' : 'none';
                        }
                    }
                }
            }
        }

        // Auch alle Elemente mit field-consumption_calc Klasse
        var consumptionFields = inlineGroup.querySelectorAll('.field-consumption_calc');
        for (var k = 0; k < consumptionFields.length; k++) {
            consumptionFields[k].style.display = show ? '' : 'none';
        }
    }

    function updateHeatingMixedFieldsVisibility(show) {
        // Zeige/Verstecke die Heizkosten-Einstellungen Fieldset
        var heatingFieldset = document.querySelector('.module:has(#id_area_percentage)');
        if (!heatingFieldset) {
            // Fallback: Suche nach dem Fieldset mit dem Text
            var fieldsets = document.querySelectorAll('fieldset');
            for (var i = 0; i < fieldsets.length; i++) {
                var legend = fieldsets[i].querySelector('h2');
                if (legend && legend.textContent.indexOf('HEATING_MIXED') !== -1) {
                    heatingFieldset = fieldsets[i];
                    break;
                }
            }
        }

        if (heatingFieldset) {
            if (show) {
                heatingFieldset.classList.remove('collapsed');
                heatingFieldset.style.display = '';
            } else {
                heatingFieldset.classList.add('collapsed');
            }
        }
    }

    function setupCostCenterAdmin() {
        var distributionTypeSelect = document.getElementById('id_distribution_type');

        if (!distributionTypeSelect) {
            return;
        }

        function updateVisibility() {
            var value = distributionTypeSelect.value;
            // CONSUMPTION and HEATING_MIXED both require consumption_calc
            var showConsumptionCalc = (value === 'CONSUMPTION' || value === 'HEATING_MIXED');
            updateInlineConsumptionCalcVisibility(showConsumptionCalc);

            // Show/hide HEATING_MIXED specific fields
            var showHeatingMixedFields = (value === 'HEATING_MIXED');
            updateHeatingMixedFieldsVisibility(showHeatingMixedFields);
        }

        // Initial ausführen
        updateVisibility();

        // Bei Änderung ausführen
        distributionTypeSelect.addEventListener('change', updateVisibility);

        // MutationObserver für dynamisch hinzugefügte Inline-Zeilen
        var inlineGroup = document.getElementById('costcentercontribution_set-group');
        if (inlineGroup) {
            var observer = new MutationObserver(function(mutations) {
                // Kurze Verzögerung damit das DOM aktualisiert ist
                setTimeout(updateVisibility, 100);
            });
            observer.observe(inlineGroup, {
                childList: true,
                subtree: true
            });
        }
    }

    // ===== Initialisierung =====
    
    function init() {
        // Prüfe auf welcher Admin-Seite wir sind
        var distributionTypeSelect = document.getElementById('id_distribution_type');
        var costCenterInput = document.getElementById('id_cost_center');

        if (distributionTypeSelect) {
            // Wir sind im CostCenter Admin
            setupCostCenterAdmin();
        } else if (costCenterInput) {
            // Wir sind im CostCenterContribution Admin
            setupCostCenterContributionAdmin();
        }
    }

    // Warte bis DOM geladen ist
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM ist bereits geladen
        init();
    }

})();
