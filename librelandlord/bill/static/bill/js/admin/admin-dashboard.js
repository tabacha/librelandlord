/**
 * LibreLandlord - Admin Dashboard Quick-Nav
 *
 * Fügt eine Quick-Navigation unter dem Admin-Header hinzu
 * mit Statistiken und Schnellzugriff auf häufige Aktionen.
 */

(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        // Quick-Nav HTML erstellen
        var quickNavHTML = [
            '<div class="quick-nav" id="quick-nav">',
            '    <div class="quick-nav-row">',
            '        <span class="quick-nav-label">📊 Übersicht:</span>',
            '        <a href="/admin/bill/apartment/" class="quick-nav-stat">🏢 <span class="num" id="stat-apartments">-</span> Wohnungen</a>',
            '        <a href="/admin/bill/renter/?move_out_date__isnull=True" class="quick-nav-stat">👥 <span class="num" id="stat-renters">-</span> Mieter</a>',
            '        <a href="/admin/bill/meter/" class="quick-nav-stat">⏱️ <span class="num" id="stat-meters">-</span> Zähler</a>',
            '        <a href="/admin/bill/costcenter/" class="quick-nav-stat">💰 <span class="num" id="stat-costcenters">-</span> Kostenstellen</a>',
            '    </div>',
            '    <div class="quick-nav-row">',
            '        <span class="quick-nav-label">⚡ Aktionen:</span>',
            '        <a href="/bill/meter-readings-input/" class="quick-nav-btn green">🔢 Zählerstände erfassen</a>',
            '        <a href="/bill/emergency-contacts/" class="quick-nav-btn red">📞 Notfallkontakte</a>',
            '        <a href="/admin/bill/bill/" class="quick-nav-btn blue">🧾 Rechnungen</a>',
            '        <a href="/admin/bill/meterreading/" class="quick-nav-btn purple">📈 Zählerstandsliste</a>',
            '    </div>',
            '    <div class="quick-nav-row">',
            '        <span class="quick-nav-label">📋 Abrechnung:</span>',
            '        <select id="year-select"><option value="">Jahr wählen...</option></select>',
            '        <select id="renter-select"><option value="">Alle Mieter / einzeln wählen...</option></select>',
            '        <button class="quick-nav-go-btn" onclick="goToBill()">→ Berechnen</button>',
            '        <button class="quick-nav-go-btn quick-nav-go-btn-tax" onclick="goToTaxOverview()">→ Steuerübersicht</button>',
            '    </div>',
            '</div>'
        ].join('\n');

        // Nach dem Header einfügen
        var header = document.getElementById('header');
        if (header) {
            header.insertAdjacentHTML('afterend', quickNavHTML);
        }

        // Statistiken laden
        fetch('/bill/api/dashboard-stats/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                document.getElementById('stat-apartments').textContent = data.apartments;
                document.getElementById('stat-renters').textContent = data.active_renters;
                document.getElementById('stat-meters').textContent = data.meters;
                document.getElementById('stat-costcenters').textContent = data.cost_centers;

                var yearSelect = document.getElementById('year-select');
                data.available_years.forEach(function(y, index) {
                    var opt = document.createElement('option');
                    opt.value = y.year;
                    opt.textContent = y.year;
                    if (index === 0) opt.selected = true;  // Neuestes Jahr vorauswählen
                    yearSelect.appendChild(opt);
                });

                // Mieter für das vorausgewählte Jahr laden
                if (data.available_years.length > 0) {
                    var firstYear = data.available_years[0];
                    var renterSelect = document.getElementById('renter-select');
                    if (firstYear.renters) {
                        firstYear.renters.forEach(function(r) {
                            var opt = document.createElement('option');
                            opt.value = r.id;
                            opt.textContent = r.apartment_number + ' - ' + r.name;
                            renterSelect.appendChild(opt);
                        });
                    }
                }

                yearSelect.addEventListener('change', function() {
                    var renterSelect = document.getElementById('renter-select');
                    renterSelect.innerHTML = '<option value="">Alle Mieter / einzeln wählen...</option>';
                    var selectedYear = data.available_years.find(function(y) { return y.year == yearSelect.value; });
                    if (selectedYear && selectedYear.renters) {
                        selectedYear.renters.forEach(function(r) {
                            var opt = document.createElement('option');
                            opt.value = r.id;
                            opt.textContent = r.apartment_number + ' - ' + r.name;
                            renterSelect.appendChild(opt);
                        });
                    }
                });
            })
            .catch(function() {});
    });

    /**
     * Navigiert zur Jahresabrechnung.
     */
    window.goToBill = function() {
        var year = document.getElementById('year-select').value;
        var renter = document.getElementById('renter-select').value;
        if (!year) { alert('Bitte Jahr wählen'); return; }
        var url = '/bill/yearly-calculation/' + year + '/';
        if (renter) url += 'renter/' + renter + '/';
        window.location.href = url;
    };

    /**
     * Navigiert zur Steuerübersicht.
     */
    window.goToTaxOverview = function() {
        var year = document.getElementById('year-select').value;
        if (!year) { alert('Bitte Jahr wählen'); return; }
        window.location.href = '/bill/tax-overview/' + year + '/';
    };
})();
