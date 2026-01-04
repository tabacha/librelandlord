#!/usr/bin/env python3
"""
Fetch meter data from remote MariaDB and output as JSON.
Usage: python fetch_meter_data.py <days_back> [--config CONFIG_FILE]

Reads database configuration from /etc/mbus_db_config.ini by default.
"""

import argparse
import configparser
import json
import sys
from datetime import datetime, timedelta

import pymysql

DEFAULT_CONFIG_FILE = '/etc/mbus_db_config.ini'


def fetch_meter_data(cursor, days_back: int) -> list:
    """Fetch heat meter data from meter_data table (one per day per meter)."""
    cutoff_date = datetime.now() - timedelta(days=days_back)

    query = """
        SELECT m.meter_id, m.energy_kwh, m.timestamp_meter
        FROM meter_data m
        INNER JOIN (
            SELECT meter_id, DATE(timestamp_meter) as reading_date, MIN(timestamp_meter) as min_ts
            FROM meter_data
            WHERE timestamp_meter >= %s
            GROUP BY meter_id, DATE(timestamp_meter)
        ) earliest ON m.meter_id = earliest.meter_id AND m.timestamp_meter = earliest.min_ts
        ORDER BY m.meter_id, m.timestamp_meter DESC
    """
    cursor.execute(query, (cutoff_date,))

    results = []
    for row in cursor.fetchall():
        ts = row[2]
        if ts and hasattr(ts, 'isoformat'):
            ts = ts.isoformat()
        value = row[1]
        if hasattr(value, '__float__'):
            value = float(value)
        results.append({
            'mbus_id': row[0],
            'value': value,
            'type': 'HE',
            'timestamp': str(ts) if ts else None
        })
    return results


def fetch_warmwater_data(cursor, days_back: int) -> list:
    """Fetch warm water data from warmwater_data table (one per day per meter)."""
    cutoff_date = datetime.now() - timedelta(days=days_back)

    query = """
        SELECT w.meter_id, w.volume_m3/1000, w.created_at
        FROM warmwater_data w
        INNER JOIN (
            SELECT meter_id, DATE(created_at) as reading_date, MIN(created_at) as min_ts
            FROM warmwater_data
            WHERE created_at >= %s
            GROUP BY meter_id, DATE(created_at)
        ) earliest ON w.meter_id = earliest.meter_id AND w.created_at = earliest.min_ts
        ORDER BY w.meter_id, w.created_at DESC
    """
    cursor.execute(query, (cutoff_date,))

    results = []
    for row in cursor.fetchall():
        ts = row[2]
        if ts and hasattr(ts, 'isoformat'):
            ts = ts.isoformat()
        value = row[1]
        if hasattr(value, '__float__'):
            value = float(value)
        results.append({
            'mbus_id': row[0],
            'value': value,
            'type': 'WW',
            'timestamp': str(ts) if ts else None
        })
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Fetch meter data from MariaDB and output as JSON'
    )
    parser.add_argument(
        'days_back',
        type=int,
        help='Number of days back to fetch (1 = today and yesterday)'
    )
    parser.add_argument(
        '--config',
        default=DEFAULT_CONFIG_FILE,
        help=f'Path to config file (default: {DEFAULT_CONFIG_FILE})'
    )

    args = parser.parse_args()

    # Read database configuration from INI file
    config = configparser.ConfigParser()
    if not config.read(args.config):
        print(
            f"Error: Could not read config file: {args.config}", file=sys.stderr)
        sys.exit(1)

    try:
        db_config = config['mysql']
    except KeyError:
        print(
            f"Error: [mysql] section not found in {args.config}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = pymysql.connect(
            host=db_config.get('host', 'localhost'),
            user=db_config.get('user'),
            password=db_config.get('password', ''),
            database=db_config.get('database', 'meter_data')
        )
        cursor = conn.cursor()

        data = fetch_meter_data(cursor, args.days_back) + \
            fetch_warmwater_data(cursor, args.days_back)

        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        print()  # Newline at end

        cursor.close()
        conn.close()

    except pymysql.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
