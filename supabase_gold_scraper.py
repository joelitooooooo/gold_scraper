#!/usr/bin/env python3
"""
Supabase Cloud Gold Scraper
Scrapes gold prices and saves directly to Supabase PostgreSQL database
"""

import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
import sys

def get_supabase_config():
    """Get Supabase configuration from GitHub secrets"""
    return {
        'url': os.environ.get('SUPABASE_URL'),
        'key': os.environ.get('SUPABASE_SERVICE_KEY')
    }

def get_eur_tl_rate():
    """Fetch current EUR/TL exchange rate"""
    try:
        url = "https://api.frankfurter.dev/v1/latest"
        params = {"base": "EUR", "symbols": "TRY"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        rate = response.json()["rates"]["TRY"]
        print(f"✅ EUR/TL Rate: {rate}")
        return rate
    except Exception as e:
        print(f"❌ FEHLER: Kann EUR/TL Kurs nicht abrufen: {e}")
        raise

def get_quarter_gold_prices():
    """Scrape quarter gold prices from BigPara"""
    url = "https://bigpara.hurriyet.com.tr/altin/ceyrek-altin-fiyati/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()

        buy_match = re.search(r'alış fiyatı (\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?) TL', text, re.I)
        sell_match = re.search(r'satış fiyatı (\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?) TL', text, re.I)

        if buy_match and sell_match:
            buy_tl = float(buy_match.group(1).replace('.', '').replace(',', '.'))
            sell_tl = float(sell_match.group(1).replace('.', '').replace(',', '.'))
            eur_tl = get_eur_tl_rate()
            return {
                'timestamp': datetime.now().isoformat(),
                'buy_price_tl': buy_tl,
                'sell_price_tl': sell_tl,
                'buy_price_eur': round(buy_tl / eur_tl, 2),
                'sell_price_eur': round(sell_tl / eur_tl, 2),
                'eur_tl_rate': eur_tl,
                'source': url,
                'scraped_from': 'github_actions'
            }
        else:
            return {'error': 'Could not extract gold prices', 'source': url}
    except Exception as e:
        return {'error': f'Scraping failed: {e}', 'source': url}

def save_to_supabase(data):
    """Insert record into Supabase"""
    if 'error' in data:
        print(f"❌ Error in data, skipping save: {data['error']}")
        return False
    cfg = get_supabase_config()
    if not cfg['url'] or not cfg['key']:
        print("❌ Missing Supabase config")
        return False
    try:
        url = f"{cfg['url']}/rest/v1/gold_prices"
        headers = {
            'apikey': cfg['key'],
            'Authorization': f"Bearer {cfg['key']}",
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        payload = {
            'date': data['timestamp'],
            'buy_price_tl': data['buy_price_tl'],
            'sell_price_tl': data['sell_price_tl'],
            'buy_price_eur': data['buy_price_eur'],
            'sell_price_eur': data['sell_price_eur'],
            'eur_tl_rate': data['eur_tl_rate'],
            'source': data['source'],
            'scraped_from': data['scraped_from']
        }
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 201:
            print("✅ Data successfully saved to Supabase!")
            print(f"📊 Record ID: {r.json()[0]['id']}")
            print(f"⏰ Timestamp: {r.json()[0]['created_at']}")
            return True
        print(f"❌ Supabase save failed: {r.status_code} – {r.text}")
        return False
    except Exception as e:
        print(f"❌ Exception saving to Supabase: {e}")
        return False

def get_recent_prices(limit=5):
    """Retrieve recent records"""
    cfg = get_supabase_config()
    if not cfg['url'] or not cfg['key']:
        return []
    try:
        r = requests.get(
            f"{cfg['url']}/rest/v1/gold_prices",
            headers={'apikey': cfg['key'], 'Authorization': f"Bearer {cfg['key']}"},
            params={'select': 'created_at,buy_price_tl,sell_price_tl,buy_price_eur,sell_price_eur',
                    'order': 'created_at.desc', 'limit': limit}
        )
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []

def show_recent_data():
    """Display recent prices safely"""
    print("\n📈 Letzte Goldpreise aus Supabase (5 neueste Einträge):")
    print("-" * 85)
    recs = get_recent_prices(5)
    if not recs:
        print("❌ Keine Daten gefunden.")
        return
    print(f"{'Datum/Zeit':<20} {'Kauf TL':<12} {'Verkauf TL':<12} {'Kauf EUR':<12} {'Verkauf EUR':<12}")
    print("-" * 85)
    for rec in recs:
        raw = rec.get('created_at', '')
        try:
            ts = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            # tolerate malformed fractions
            try:
                ts = datetime.strptime(raw.split('+')[0].split('.')[0], '%Y-%m-%dT%H:%M:%S')
            except Exception:
                ts = datetime.utcnow()
        ds = ts.strftime('%d.%m.%Y %H:%M')
        bt, st = rec.get('buy_price_tl') or 0, rec.get('sell_price_tl') or 0
        be, se = rec.get('buy_price_eur') or 0, rec.get('sell_price_eur') or 0
        print(f"{ds:<20} {bt:>8.2f}      {st:>8.2f}      {be:>8.2f}      {se:>8.2f}")

def main():
    print("🔍 Supabase Cloud Gold Scraper Starting...")
    print(f"⏰ Current time: {datetime.now().isoformat()}")
    print("=" * 50)
    cfg = get_supabase_config()
    if not cfg['url'] or not cfg['key']:
        print("❌ FEHLER: Supabase-Konfiguration fehlt!")
        sys.exit(1)
    print("✅ Supabase configuration found")
    print("\n🔍 Scraping gold prices from BigPara...")
    data = get_quarter_gold_prices()
    if 'error' not in data:
        print("✅ Successfully scraped gold prices:")
        print(f"   Buy TL:  {data['buy_price_tl']:,.2f}")
        print(f"   Sell TL: {data['sell_price_tl']:,.2f}")
        print(f"   Buy EUR: {data['buy_price_eur']:,.2f}")
        print(f"   Sell EUR:{data['sell_price_eur']:,.2f}")
    else:
        print(f"❌ Scraping failed: {data['error']}")
    print("\n💾 Saving to Supabase...")
    if save_to_supabase(data):
        print("\n✅ CLOUD SCRAPING COMPLETED SUCCESSFULLY!")
        show_recent_data()
    else:
        print("\n❌ Cloud scraping failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
