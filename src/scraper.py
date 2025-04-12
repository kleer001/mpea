import asyncio
import logging
import os
from urllib.parse import quote

from browser import BrowserManager
from extraction import ExtractionManager

class MarketplaceScraper:
    # Map of supported cities to their Facebook Marketplace location identifiers
    SUPPORTED_LOCATIONS = {
        "vancouver": "vancouver/", 
        "seattle": "seattle/",
        "portland": "portland/", 
        "san francisco": "sanfrancisco/",
        "los angeles": "losangeles/",
        "new york": "newyork/",
        "chicago": "chicago/",
        "toronto": "toronto/",
        "montreal": "montreal/",
        "london": "london/",
        "sydney": "sydney/",
        "melbourne": "melbourne/"
    }
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.search_params = self.config.get_search_params()
        self.user_data_dir = "browser_data"
        self.storage_state_path = os.path.join(self.user_data_dir, "storage_state.json")
        
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
        
        self.browser_manager = BrowserManager(self.user_data_dir, self.storage_state_path)
        self.extraction_manager = None
    
    def _get_location_identifier(self, location_name):
        """Convert a location name from the config to the proper Facebook URL format."""
        if not location_name:
            return ""
            
        # Convert to lowercase for case-insensitive matching
        location_name = location_name.lower()
        
        # Try exact match first
        if location_name in self.SUPPORTED_LOCATIONS:
            return self.SUPPORTED_LOCATIONS[location_name]
            
        # Try partial match
        for supported_location, identifier in self.SUPPORTED_LOCATIONS.items():
            if supported_location in location_name or location_name in supported_location:
                logging.info(f"Using location '{supported_location}' for search parameter '{location_name}'")
                return identifier
                
        # If no match, log a warning and return empty string
        logging.warning(f"Location '{location_name}' not found in supported locations. Using default location.")
        return ""
    
    def _build_search_url(self):
        keywords = quote(self.search_params['keywords'])
        location_name = self.search_params['location'] if 'location' in self.search_params else ""
        location_identifier = self._get_location_identifier(location_name)
        min_price = int(self.search_params['min_price'])
        max_price = int(self.search_params['max_price'])
        
        # Build URL with location if available
        base_url = "https://www.facebook.com/marketplace/"
        if location_identifier:
            url = f"{base_url}{location_identifier}search?query={keywords}"
        else:
            url = f"{base_url}search?query={keywords}"
        
        if min_price > 0 or max_price > 0:
            url += f"&minPrice={min_price}&maxPrice={max_price}"
            
        logging.info(f"Built search URL with location '{location_name}' → '{location_identifier}'")
        return url
    
    async def search_marketplace(self):
        results = []
        try:
            search_url = self._build_search_url()
            logging.info(f"Navigating to: {search_url}")
            
            page = self.browser_manager.page
            await page.goto(search_url, wait_until="domcontentloaded")
            await self.browser_manager.random_wait(reason="after initial page load")
            
            await self.browser_manager.handle_initial_dialogs()
            
            self.extraction_manager = ExtractionManager(page)
            
            for attempt in range(3):
                try:
                    await self.browser_manager.simulate_human_behavior()
                    
                    results = await self.extraction_manager.extract_via_multiple_strategies()
                    
                    if results:
                        logging.info(f"Successfully extracted data for {len(results)} listings on attempt {attempt+1}")
                        break
                    else:
                        logging.warning(f"No results found on attempt {attempt+1}, retrying...")
                        await self.browser_manager.random_wait(3, 5, "before retry")
                except Exception as e:
                    logging.warning(f"Error during extraction attempt {attempt+1}: {e}")
                    await self.browser_manager.random_wait(3, 5, "after error")
            
            if not results:
                await page.screenshot(path="no_results.png")
                logging.error("All extraction attempts failed")
            
            # Results should already have cleaned URLs from extraction manager
            # Remove duplicates by URL
            unique_results = []
            seen_urls = set()
            for item in results[:20]:  # Limit to first 20 results
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_results.append(item)
            
            return unique_results
            
        except Exception as e:
            logging.error(f"Error during marketplace search: {e}")
            await self.browser_manager.page.screenshot(path="error.png")
            self.config.set_active(False)
            return []
    
    async def run_search(self):
        if not self.config.is_active():
            logging.info("Search is not active. Skipping.")
            return []
        
        try:
            await self.browser_manager.initialize()
            results = await self.search_marketplace()
            return results
        finally:
            await self.browser_manager.close()

if __name__ == "__main__":
    from config import ConfigManager
    
    logging.basicConfig(level=logging.INFO)
    config = ConfigManager()
    
    async def test_scraper():
        scraper = MarketplaceScraper(config)
        results = await scraper.run_search()
        for item in results:
            print(f"{item['title']} - ${item['price']} - {item['url']}")
    
    asyncio.run(test_scraper())