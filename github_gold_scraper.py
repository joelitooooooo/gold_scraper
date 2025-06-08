#!/usr/bin/env python3
"""
GitHub Cloud Gold Scraper
Scrapes gold prices and saves to JSON files for later local sync
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import os
import sys

def ensure_data_directory():
    """
    Create data directory if it doesn't exist
    """
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists('data/pending'):
        os.makedirs('data/pending')

def get_eur_tl_rate():
    """
    Get current EUR/TL exchange rate using Frankfurter API
    """
    try:
        url = "https://api.frankfurter.dev/v1/latest"
        params = {"base": "EUR", "symbols": "TRY"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()["rates"]["TRY"]
    except:
        return 36.50  # Fallback rate

def get_quarter_gold_prices():
    """
    Scrapes quarter gold prices from BigPara website
    """
    url = "https://bigpara.hurriyet.com.tr/altin/ceyrek-altin-fiyati/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text()
        
        # Extract prices using regex
        buy_pattern = r'alış fiyatı (\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?) TL'
        sell_pattern = r'satış fiyatı (\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?) TL'
        
        buy_match = re.search(buy_pattern, page_text, re.IGNORECASE)
        sell_match = re.search(sell_pattern, page_text, re.IGNORECASE)
        
        gold_data = {}
        
        if buy_match and sell_match:
            buy_price_tl = float(buy_match.group(1).replace('.', '').replace(',', '.'))
            sell_price_tl = float(sell_match.group(1).replace('.', '').replace(',', '.'))
            
            # Get EUR conversion
            eur_tl_rate = get_eur_tl_rate()
            
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
        else:
            gold_data = {
                'error': 'Could not extract gold prices from website',
                'timestamp': datetime.now().isoformat(),
                'source': url
            }
        
        return gold_data
        
    except Exception as e:
        return {
            'error': f'Scraping failed: {str(e)}',
            'timestamp': datetime.now().isoformat(),
            'source': url
        }

def save_to_json(gold_data):
    """
    Save scraped data to JSON file for later sync
    """
    ensure_data_directory()
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/pending/gold_prices_{timestamp}.json"
    
    # Add metadata
    gold_data['saved_at'] = datetime.now().isoformat()
    gold_data['filename'] = filename
    gold_data['sync_status'] = 'pending'
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(gold_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Data saved to {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ Error saving to JSON: {e}")
        return None

def update_summary():
    """
    Update summary file with latest data count
    """
    try:
        pending_files = [f for f in os.listdir('data/pending') if f.endswith('.json')]
        
        summary = {
            'last_update': datetime.now().isoformat(),
            'pending_records': len(pending_files),
            'latest_files': sorted(pending_files, reverse=True)[:10]  # Last 10 files
        }
        
        with open('data/sync_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        print(f"📊 Summary updated: {len(pending_files)} pending records")
        
    except Exception as e:
        print(f"❌ Error updating summary: {e}")

def main():
    """
    Main scraping function for GitHub Actions
    """
    print("🔍 GitHub Actions Gold Scraper Starting...")
    print(f"⏰ Current time: {datetime.now().isoformat()}")
    print("=" * 50)
    
    # Scrape gold prices
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
    
    # Save to JSON
    filename = save_to_json(gold_data)
    
    if filename:
        # Update summary
        update_summary()
        print("🚀 Cloud scraping completed successfully!")
    else:
        print("❌ Cloud scraping failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
