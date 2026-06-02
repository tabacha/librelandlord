from datetime import timedelta
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

import bill.middleware as middleware_module
from bill.middleware import (
    BLOCK_EXPIRY,
    AttackBlocklistMiddleware,
    _blocklist,
    _db_synced,
    _normalize_ip,
    _is_suspicious,
)


def _get_response_404(request):
    return HttpResponse(status=404)


def _get_response_200(request):
    return HttpResponse(status=200)


class NormalizeIPTest(TestCase):
    def test_ipv4_maps_to_26(self):
        self.assertEqual(_normalize_ip('1.2.3.100'), '1.2.3.64/26')
        self.assertEqual(_normalize_ip('10.0.0.1'), '10.0.0.0/26')
        self.assertEqual(_normalize_ip('192.168.1.63'), '192.168.1.0/26')

    def test_ipv6_maps_to_48(self):
        self.assertEqual(_normalize_ip('2001:db8:1234:5678::1'), '2001:db8:1234::/48')
        self.assertEqual(_normalize_ip('2001:db8:1234::'), '2001:db8:1234::/48')

    def test_invalid_ip_passthrough(self):
        self.assertEqual(_normalize_ip('not-an-ip'), 'not-an-ip')
        self.assertEqual(_normalize_ip(''), '')


class SuspiciousPathTest(TestCase):
    def test_php_files_are_suspicious(self):
        self.assertTrue(_is_suspicious('/style.php'))
        self.assertTrue(_is_suspicious('/wp-admin/admin-ajax.php'))
        self.assertTrue(_is_suspicious('/WP-ADMIN/STYLE.PHP'))  # case-insensitive

    def test_wordpress_paths_are_suspicious(self):
        self.assertTrue(_is_suspicious('/wp-content/plugins/foo.js'))
        self.assertTrue(_is_suspicious('/wp-includes/functions.js'))
        self.assertTrue(_is_suspicious('/wp-login'))

    def test_other_attack_paths_are_suspicious(self):
        self.assertTrue(_is_suspicious('/.env'))
        self.assertTrue(_is_suspicious('/.git/config'))
        self.assertTrue(_is_suspicious('/phpmyadmin/'))
        self.assertTrue(_is_suspicious('/cgi-bin/test'))
        self.assertTrue(_is_suspicious('/shell'))
        self.assertTrue(_is_suspicious('/xmlrpc.xml'))

    def test_legitimate_paths_are_not_suspicious(self):
        self.assertFalse(_is_suspicious('/robots.txt'))
        self.assertFalse(_is_suspicious('/sitemap.xml'))
        self.assertFalse(_is_suspicious('/favicon.ico'))
        self.assertFalse(_is_suspicious('/admin/'))
        self.assertFalse(_is_suspicious('/bill/'))
        self.assertFalse(_is_suspicious('/'))


class BlocklistMiddlewareTest(TestCase):
    def setUp(self):
        _blocklist.clear()
        _db_synced.clear()
        middleware_module._initialized = True  # DB-Laden überspringen
        self.factory = RequestFactory()

    def _request(self, path, ip='1.2.3.100'):
        req = self.factory.get(path)
        req.META['HTTP_X_REAL_IP'] = ip
        return req

    def _middleware(self, get_response=_get_response_404):
        return AttackBlocklistMiddleware(get_response)

    # --- Blocking ---

    @patch('bill.middleware._db_save')
    def test_suspicious_404_blocks_network(self, mock_db_save):
        mw = self._middleware()
        response = mw(self._request('/wp-admin/style.php'))
        self.assertEqual(response.status_code, 404)  # erste Anfrage durch
        self.assertIn('1.2.3.64/26', _blocklist)
        mock_db_save.assert_called_once()

    @patch('bill.middleware._db_save')
    def test_blocked_ip_gets_403_on_any_path(self, _):
        mw = self._middleware()
        mw(self._request('/wp-admin/style.php'))            # Block auslösen
        response = mw(self._request('/robots.txt'))          # legitimer Pfad, trotzdem geblockt
        self.assertEqual(response.status_code, 403)

    @patch('bill.middleware._db_save')
    def test_legitimate_404_does_not_block(self, mock_db_save):
        mw = self._middleware()
        mw(self._request('/robots.txt'))
        self.assertNotIn('1.2.3.64/26', _blocklist)
        mock_db_save.assert_not_called()

    @patch('bill.middleware._db_save')
    def test_200_on_suspicious_path_does_not_block(self, mock_db_save):
        mw = self._middleware(_get_response_200)
        mw(self._request('/wp-admin/style.php'))
        self.assertNotIn('1.2.3.64/26', _blocklist)
        mock_db_save.assert_not_called()

    # --- IPv6 /48 ---

    @patch('bill.middleware._db_save')
    def test_ipv6_blocks_entire_48_network(self, _):
        mw = self._middleware()
        mw(self._request('/shell.php', ip='2001:db8:1234:5678::1'))
        self.assertIn('2001:db8:1234::/48', _blocklist)

        # Andere Adresse im selben /48 wird ebenfalls geblockt
        response = mw(self._request('/robots.txt', ip='2001:db8:1234:9999::2'))
        self.assertEqual(response.status_code, 403)

    # --- Ablauf nach 24h ---

    @patch('bill.middleware._db_delete')
    @patch('bill.middleware._db_save')
    def test_block_expires_after_24h_silence(self, _, mock_db_delete):
        mw = self._middleware()
        mw(self._request('/wp-admin/style.php'))

        # Timestamp auf 25h in der Vergangenheit setzen
        _blocklist['1.2.3.64/26'] = timezone.now() - BLOCK_EXPIRY - timedelta(hours=1)

        response = mw(self._request('/robots.txt'))
        self.assertEqual(response.status_code, 404)          # wieder durchgelassen
        self.assertNotIn('1.2.3.64/26', _blocklist)
        mock_db_delete.assert_called_once_with('1.2.3.64/26')

    @patch('bill.middleware._db_save')
    def test_activity_resets_expiry_timer(self, _):
        mw = self._middleware()
        mw(self._request('/wp-admin/style.php'))

        # Fast abgelaufen (23h)
        _blocklist['1.2.3.64/26'] = timezone.now() - timedelta(hours=23)

        response = mw(self._request('/something'))
        self.assertEqual(response.status_code, 403)          # noch geblockt

    # --- IP-Erkennung via Nginx-Header ---

    @patch('bill.middleware._db_save')
    def test_x_real_ip_header_is_used(self, _):
        mw = self._middleware()
        req = self.factory.get('/shell.php')
        req.META['HTTP_X_REAL_IP'] = '5.6.7.8'
        mw(req)
        self.assertIn('5.6.7.0/26', _blocklist)

    @patch('bill.middleware._db_save')
    def test_x_forwarded_for_last_entry_used_as_fallback(self, _):
        mw = self._middleware()
        req = self.factory.get('/shell.php')
        req.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 5.6.7.8'  # letzter = echter Client
        mw(req)
        self.assertIn('5.6.7.0/26', _blocklist)
