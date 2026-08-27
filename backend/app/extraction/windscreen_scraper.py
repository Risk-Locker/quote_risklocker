import urllib.request
import re
from typing import Optional, Dict

class WindscreenScraper:
    """
    Scraper to extract windscreen Sum Insured and calculated Premium (15%)
    based on the vehicle model from Autoglass.com.my.
    """
    URL = 'https://www.autoglass.com.my/insurance-pricelist.html'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def __init__(self):
        self.pricing_data = {}
        self._cache_data()

    def _cache_data(self):
        """Fetches and parses the HTML to build a lookup dictionary."""
        try:
            req = urllib.request.Request(self.URL, headers=self.HEADERS)
            response = urllib.request.urlopen(req)
            html = response.read().decode('utf-8', errors='ignore')
            
            # Simple regex to extract the table rows
            row_pattern = re.compile(r'<tr>(.*?)</tr>', re.IGNORECASE | re.DOTALL)
            td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
            
            rows = row_pattern.findall(html)
            for row in rows:
                cols = td_pattern.findall(row)
                if len(cols) >= 3:
                    model = self._clean_text(cols[0])
                    coverage_str = self._clean_text(cols[1])
                    
                    if 'RM' in coverage_str.upper():
                        try:
                            # Extract numeric value
                            coverage_val = float(re.sub(r'[^\d.]', '', coverage_str))
                            self.pricing_data[model.lower()] = coverage_val
                        except ValueError:
                            continue
        except Exception as e:
            print(f"[WindscreenScraper] Failed to fetch data: {e}")

    def _clean_text(self, text: str) -> str:
        """Removes HTML tags and cleans up whitespace."""
        clean = re.sub(r'<[^>]+>', '', text)
        return ' '.join(clean.split()).strip()

    def get_windscreen_pricing(self, car_model: str) -> Optional[Dict[str, float]]:
        """
        Looks up the car model in the cached data. 
        Returns a dict with 'sum_insured' and 'cost' (15% of sum insured).
        """
        if not self.pricing_data:
            return None

        car_model_lower = car_model.lower().strip()
        
        # 1. Exact Match
        if car_model_lower in self.pricing_data:
            sum_insured = self.pricing_data[car_model_lower]
            return {
                'model_matched': car_model_lower,
                'sum_insured': sum_insured,
                'cost': round(sum_insured * 0.15, 2)
            }

        # 2. Partial Match (find best substring match)
        best_match = None
        for model_key, sum_insured in self.pricing_data.items():
            if car_model_lower in model_key or model_key in car_model_lower:
                best_match = (model_key, sum_insured)
                break # Just take the first reasonable match for now

        if best_match:
            sum_insured = best_match[1]
            return {
                'model_matched': best_match[0],
                'sum_insured': sum_insured,
                'cost': round(sum_insured * 0.15, 2)
            }

        return None

if __name__ == '__main__':
    scraper = WindscreenScraper()
    print("Testing Windscreen Scraper...")
    
    test_models = ['Perodua Myvi', 'Honda Civic', 'Proton X70', 'Unknown Car']
    for model in test_models:
        result = scraper.get_windscreen_pricing(model)
        if result:
            print(f"[FOUND] '{model}' -> Matched as '{result['model_matched']}': Sum Insured RM{result['sum_insured']}, Premium RM{result['cost']}")
        else:
            print(f"[MISSING] '{model}' not found in pricelist.")
