#!/bin/bash

# Build-Script für Font Awesome lokale Installation
# Kopiert CSS und Webfonts von node_modules in Django static files

echo "Building Font Awesome assets..."

# Stelle sicher, dass die Zielverzeichnisse existieren
mkdir -p librelandlord/bill/static/bill/css
mkdir -p librelandlord/bill/static/bill/webfonts

# Kopiere CSS
cp node_modules/@fortawesome/fontawesome-free/css/all.min.css librelandlord/bill/static/bill/css/

# Kopiere Webfonts
cp node_modules/@fortawesome/fontawesome-free/webfonts/*.woff2 librelandlord/bill/static/bill/webfonts/

# Korrigiere Font-Pfade in CSS für Django static files
echo "Fixing font paths in CSS for Django..."
sed -i 's|url(../webfonts/|url(/static/bill/webfonts/|g' librelandlord/bill/static/bill/css/all.min.css

echo "Font Awesome assets successfully copied to static files"
echo "- CSS: librelandlord/bill/static/bill/css/all.min.css"
echo "- Fonts: librelandlord/bill/static/bill/webfonts/*.woff2"
echo "- Font paths in CSS updated for Django static files"
