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
    """
    Get Supabase configuration from GitHub secrets
    """
    return {
        'url': os.environ.get('SUPABASE_URL'),
        'key': os.environ.get('SUPABASE_SERVICE_KEY')
    }

def get_eur_tl_rate():
    """
    Get current EUR/TL exchange rate using Frankfurter API
    Raises exception if rate cannot be fetched
    """
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
        raise Exception(f"EUR/TL rate fetch failed: {e}")

def get_quarter_gold_prices():
    """
    Scrapes quarter gold prices from BigPara website
    """
    url = "https://bigpara.hurriyet.com.tr/altin/ceyrek-altin-fiyati/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text()
        
        # Extract prices using regex patterns
        buy_pattern = r'alış fiyatı (\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?) TL'
        sell_pattern = r'satış fiyatı (\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?) TL'
        
        buy_match = re.search(buy_pattern, page_text, re.IGNORECASE)
        sell_match = re.search(sell_pattern, page_text, re.IGNORECASE)
        
        if buy_match and sell_match:
            # Parse prices
            buy_price_tl = float(buy_match.group(1).replace('.', '').replace(',', '.'))
            sell_price_tl = float(sell_match.group(1).replace('.', '').replace(',', '.'))
            
            # Get EUR conversion - MUST succeed or fail
            try:
                eur_tl_rate = get_eur_tl_rate()
            except Exception as e:
                return {
                    'error': f'EUR/TL rate fetch failed: {str(e)}',
                    'timestamp': datetime.now().isoformat(),
                    'source': url
                }
            
            gold_data = {
                'timestamp': datetime.now().isoformat(),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'buy_price_tl': buy_price_tl,
                'sell_price_tl': sell_price_tl,
                'buy_price_eur': round(buy_price_tl / eur_tl_rate, 2),
                'sell_price_eur': round(sell_price_tl / eur_tl_rate, 2),
                'eur_tl_rate': eur_tl_rate,
                'source': url,
                'scraped_from': 'github_actions'
            }
            
            return gold_data
        else:
            return {
                'error': 'Could not extract gold prices from website',
                'timestamp': datetime.now().isoformat(),
                'source': url
            }
        
    except Exception as e:
        return {
            'error': f'Scraping failed: {str(e)}',
            'timestamp': datetime.now().isoformat(),
            'source': url
        }

def save_to_supabase(gold_data):
    """
    Save gold data to Supabase PostgreSQL database
    """
    if 'error' in gold_data:
        print(f"❌ Error in data, skipping save: {gold_data['error']}")
        return False
    
    config = get_supabase_config()
    if not config['url'] or not config['key']:
        print("❌ Supabase configuration missing!")
        print("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in GitHub secrets")
        return False
    
    try:
        # Prepare data for Supabase
        db_data = {
            'date': gold_data['timestamp'],
            'buy_price_tl': gold_data['buy_price_tl'],
            'sell_price_tl': gold_data['sell_price_tl'],
            'buy_price_eur': gold_data['buy_price_eur'],
            'sell_price_eur': gold_data['sell_price_eur'],
            'eur_tl_rate': gold_data['eur_tl_rate'],
            'source': gold_data['source'],
            'scraped_from': gold_data['scraped_from']
        }
        
        # Insert into Supabase via REST API
        url = f"{config['url']}/rest/v1/gold_prices"
        headers = {
            'apikey': config['key'],
            'Authorization': f"Bearer {config['key']}",
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        
        response = requests.post(url, json=db_data, headers=headers)
        
        if response.status_code == 201:
            result = response.json()[0]
            print(f"✅ Data successfully saved to Supabase!")
            print(f"📊 Record ID: {result['id']}")
            print(f"🏦 Database: Supabase PostgreSQL")
            print(f"📋 Table: gold_prices")
            print(f"⏰ Timestamp: {result['created_at']}")
            return True
        else:
            print(f"❌ Supabase save failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception saving to Supabase: {e}")
        return False

def get_recent_prices(limit=5):
    """
    Get recent prices from Supabase for display
    """
    config = get_supabase_config()
    if not config['url'] or not config['key']:
        return []
    
    try:
        url = f"{config['url']}/rest/v1/gold_prices"
        headers = {
            'apikey': config['key'],
            'Authorization': f"Bearer {config['key']}"
        }
        params = {
            'select': 'created_at,buy_price_tl,sell_price_tl,buy_price_eur,sell_price_eur',
            'order': 'created_at.desc',
            'limit': limit
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Could not fetch recent prices: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"⚠️ Error fetching recent prices: {e}")
        return []

def show_recent_data():
    """
    Display recent price data from Supabase
    """
    print("\n📈 Letzte Goldpreise aus Supabase (5 neueste Einträge):")
    print("-" * 85)
    
    recent_prices = get_recent_prices(5)
    
    if not recent_prices:
        print("❌ Keine Daten in der Datenbank gefunden.")
        return
    
    print(f"{'Datum/Zeit':<20} {'Kauf TL':<12} {'Verkauf TL':<12} {'Kauf EUR':<12} {'Verkauf EUR':<12}")
    print("-" * 85)
    
    for record in recent_prices:
        # Parse ISO datetime
        created_at = datetime.fromisoformat(record['created_at'].replace('Z', '+00:00'))
        date_str = created_at.strftime("%d.%m.%Y %H:%M")
        
        buy_tl = f"{record['buy_price_tl']:.2f}" if record['buy_price_tl'] else 'N/A'
        sell_tl = f"{record['sell_price_tl']:.2f}" if record['sell_price_tl'] else 'N/A'
        buy_eur = f"{record['buy_price_eur']:.2f}" if record['buy_price_eur'] else 'N/A'
        sell_eur = f"{record['sell_price_eur']:.2f}" if record['sell_price_eur'] else 'N/A'
        
        print(f"{date_str:<20} {buy_tl:<12} {sell_tl:<12} {buy_eur:<12} {sell_eur:<12}")

def main():
    """
    Main scraping function for GitHub Actions with Supabase
    """
    print("🔍 Supabase Cloud Gold Scraper Starting...")
    print(f"⏰ Current time: {datetime.now().isoformat()}")
    print("=" * 50)
    
    # Check Supabase configuration
    config = get_supabase_config()
    if not config['url'] or not config['key']:
        print("❌ FEHLER: Supabase-Konfiguration fehlt!")
        print("Bitte setzen Sie SUPABASE_URL und SUPABASE_SERVICE_KEY in GitHub Secrets")
        sys.exit(1)
    
    print("✅ Supabase configuration found")
    
    # Scrape gold prices
    print("\n🔍 Scraping gold prices from BigPara...")
    gold_data = get_quarter_gold_prices()
    
    # Display results
    if 'error' not in gold_data:
        print("✅ Successfully scraped gold prices:")
        print(f"   Buy TL:  {gold_data['buy_price_tl']:,.2f}")
        print(f"   Sell TL: {gold_data['sell_price_tl']:,.2f}")
        print(f"   Buy EUR: {gold_data['buy_price_eur']:,.2f}")
        print(f"   Sell EUR: {gold_data['sell_price_eur']:,.2f}")
        print(f"   EUR/TL Rate: {gold_data['eur_tl_rate']}")
    else:
        print(f"❌ Scraping failed: {gold_data['error']}")
    
    # Save to Supabase
    print("\n💾 Saving to Supabase...")
    success = save_to_supabase(gold_data)
    
    if success:
        print("\n✅ CLOUD SCRAPING COMPLETED SUCCESSFULLY!")
        show_recent_data()
    else:
        print("\n❌ Cloud scraping failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
