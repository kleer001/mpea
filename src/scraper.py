import asyncio
import logging
import random
import re
import os
import json
import time
from playwright.async_api import async_playwright, TimeoutError
from urllib.parse import quote

class MarketplaceScraper:
    def __init__(self, config_manager):
        self.config = config_manager
        self.search_params = self.config.get_search_params()
        self.browser = None
        self.context = None
        self.page = None
        self.user_data_dir = "browser_data"
        self.storage_state_path = os.path.join(self.user_data_dir, "storage_state.json")
        
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
    
    async def random_wait(self, min_time=4, max_time=8, reason=None):
        wait_time = random.uniform(min_time, max_time)
        if reason:
            logging.info(f"Waiting for {wait_time:.2f} seconds: {reason}")
        else:
            logging.info(f"Waiting for {wait_time:.2f} seconds")
        await asyncio.sleep(wait_time)
    
    async def initialize(self):
        self.playwright = await async_playwright().start()
        
        context_params = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080}
        }
        
        if os.path.exists(self.storage_state_path):
            context_params["storage_state"] = self.storage_state_path
            
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(**context_params)
        
        await self._apply_stealth_mode()
        
        self.page = await self.context.new_page()
    
    async def _apply_stealth_mode(self):
        await self.context.add_init_script("""
            () => {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                
                window.navigator.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {
                                type: 'application/x-google-chrome-pdf',
                                suffixes: 'pdf',
                                description: 'Portable Document Format',
                                enabledPlugin: true,
                            },
                            name: 'Chrome PDF Plugin',
                            filename: 'internal-pdf-viewer',
                            description: 'Portable Document Format',
                        },
                    ],
                });
            }
        """)
    
    async def simulate_human_behavior(self):
        viewport_height = await self.page.evaluate("window.innerHeight")
        document_height = await self.page.evaluate("document.body.scrollHeight")
        
        scroll_steps = random.randint(3, 6)
        for i in range(scroll_steps):
            scroll_amount = random.randint(100, 800)
            await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self.random_wait(1, 3, "scrolling the page")
            
            try:
                await self.page.evaluate("""
                    () => {
                        const loadMoreButton = Array.from(document.querySelectorAll('div[role="button"]'))
                            .find(el => el.textContent.includes('See More') || 
                                        el.textContent.includes('Load More') ||
                                        el.textContent.includes('Show more results'));
                        if (loadMoreButton) loadMoreButton.click();
                    }
                """)
            except Exception:
                pass
        
        random_coords = []
        for _ in range(random.randint(3, 7)):
            x = random.randint(100, 800)
            y = random.randint(100, viewport_height - 100)
            random_coords.append((x, y))
            
        for x, y in random_coords:
            await self.page.mouse.move(x, y)
            await self.random_wait(0.1, 0.5, "moving mouse")
    
    async def save_session(self):
        await self.context.storage_state(path=self.storage_state_path)
        logging.info("Saved browser session state")
    
    async def close(self):
        if self.context:
            await self.save_session()
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    def _build_search_url(self):
        keywords = quote(self.search_params['keywords'])
        location = quote(self.search_params['location']) if self.search_params['location'] else ""
        min_price = int(self.search_params['min_price'])
        max_price = int(self.search_params['max_price'])
        
        if location:
            url = f"https://www.facebook.com/marketplace/{location}/search?query={keywords}"
        else:
            url = f"https://www.facebook.com/marketplace/search?query={keywords}"
        
        if min_price > 0 or max_price > 0:
            url += f"&minPrice={min_price}&maxPrice={max_price}"
            
        return url
    
    async def handle_initial_dialogs(self):
        try:
            dialog_patterns = [
                'button[aria-label="Close"]',
                'button:has-text("Accept")',
                'button:has-text("Allow")',
                'button:has-text("Not Now")',
                'button:has-text("I Accept")',
                'button:has-text("OK")',
                'button:has-text("Continue")'
            ]
            
            for pattern in dialog_patterns:
                button = self.page.locator(pattern)
                if await button.count() > 0:
                    logging.info(f"Found dialog button: {pattern}")
                    await button.click()
                    await self.random_wait(2, 4, f"after clicking {pattern}")
        
        except Exception as e:
            logging.warning(f"Error handling initial dialogs: {e}")
    
    async def extract_listings_via_javascript(self):
        return await self.page.evaluate("""
            () => {
                const results = [];
                
                const extractPrice = (text) => {
                    const priceMatch = text.match(/(?:CA\\$|£|\\$|€)([0-9,.]+)/);
                    return priceMatch ? parseFloat(priceMatch[1].replace(/,/g, '')) : 0;
                };
                
                const extractTitle = (text) => {
                    const lines = text.split('\\n').map(line => line.trim()).filter(Boolean);
                    for (const line of lines) {
                        if (!line.match(/(?:CA\\$|£|\\$|€)[0-9,.]+/) && 
                            !['Log In', 'Marketplace'].includes(line) && 
                            line.length > 3 && 
                            !line.includes('Marketplace') && 
                            !line.includes('Sponsored') && 
                            !line.includes('· ')) {
                            return line;
                        }
                    }
                    return "Unknown Title";
                };
                
                const extractListingId = (url) => {
                    const match = url.match(/\\/item\\/([^\\/\\?]+)/);
                    return match ? match[1] : "unknown";
                };
                
                // First strategy: Find all marketplace item links
                const itemLinks = Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'));
                
                // Extract data from each listing container
                for (const link of itemLinks) {
                    // Get the href attribute
                    const url = link.href;
                    
                    // Get the listing container (parent elements)
                    let container = link;
                    for (let i = 0; i < 5; i++) {
                        container = container.parentElement;
                        if (!container) break;
                        
                        // Look for price text in this container
                        const containerText = container.innerText || '';
                        if (containerText.match(/(?:CA\\$|£|\\$|€)[0-9,.]+/)) {
                            // This container has price text, so it might be our listing container
                            const title = extractTitle(containerText);
                            const price = extractPrice(containerText);
                            const id = extractListingId(url);
                            
                            results.push({
                                id,
                                title,
                                price,
                                url
                            });
                            
                            break;
                        }
                    }
                }
                
                // Deduplicate results by URL
                const uniqueResults = [];
                const seenUrls = new Set();
                
                for (const result of results) {
                    if (!seenUrls.has(result.url)) {
                        seenUrls.add(result.url);
                        uniqueResults.push(result);
                    }
                }
                
                return uniqueResults;
            }
        """)
    
    async def extract_listings_via_xpath(self):
        results = []
        
        try:
            xpath_strategies = [
                "//div[.//a[contains(@href, '/marketplace/item/')] and .//*[contains(text(), '$')]]",
                "//div[@role='article' and .//a[contains(@href, '/marketplace/item/')]]",
                "//*[@data-testid='marketplace_feed_item']",
                "//div[.//a[contains(@href, '/marketplace/item/')] and .//*[contains(@aria-label, 'Price')]]"
            ]
            
            for strategy in xpath_strategies:
                containers = await self.page.evaluate(f"""
                    (xpath) => {{
                        const containers = [];
                        const elements = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                        for (let i = 0; i < elements.snapshotLength; i++) {{
                            containers.push(elements.snapshotItem(i));
                        }}
                        return containers.length;
                    }}
                """, strategy)
                
                if containers > 0:
                    logging.info(f"Found {containers} containers using XPath: {strategy}")
                    
                    listing_data = await self.page.evaluate(f"""
                        (xpath) => {{
                            const results = [];
                            const extractPrice = (text) => {{
                                const priceMatch = text.match(/(?:CA\\$|£|\\$|€)([0-9,.]+)/);
                                return priceMatch ? parseFloat(priceMatch[1].replace(/,/g, '')) : 0;
                            }};
                            
                            const isValidTitle = (text) => {{
                                if (!text || text.length < 4) return false;
                                if (['Log In', 'Marketplace'].includes(text)) return false;
                                if (text.includes('Marketplace')) return false;
                                if (text.includes('Sponsored')) return false;
                                if (text.includes('· ')) return false;
                                if (text.includes('Log in')) return false;
                                if (text.match(/^\\d+$/)) return false;
                                return true;
                            }};
                            
                            const containers = [];
                            const elements = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                            for (let i = 0; i < elements.snapshotLength; i++) {{
                                containers.push(elements.snapshotItem(i));
                            }}
                            
                            const seenUrls = new Set();
                            
                            for (const container of containers) {{
                                // Find the link to the item
                                const linkElement = document.evaluate(".//a[contains(@href, '/marketplace/item/')]", container, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (!linkElement) continue;
                                
                                const url = linkElement.href;
                                
                                // Skip if we've already seen this URL
                                if (seenUrls.has(url)) continue;
                                seenUrls.add(url);
                                
                                const containerText = container.innerText || '';
                                
                                // Extract listing ID
                                const idMatch = url.match(/\\/item\\/([^\\/\\?]+)/);
                                const id = idMatch ? idMatch[1] : "unknown";
                                
                                // Extract price
                                let price = 0;
                                // Try to find price by aria-label first
                                const priceElement = document.evaluate(".//*[@aria-label='Price' or contains(@data-ms, 'price')]", container, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (priceElement) {{
                                    price = extractPrice(priceElement.textContent);
                                }} else {{
                                    // Fall back to extracting from all text
                                    price = extractPrice(containerText);
                                }}
                                
                                // Extract title
                                let title = "Unknown Title";
                                
                                // Try to find title by aria-label or data attribute
                                const titleElement = document.evaluate(".//*[@aria-label='Title' or contains(@data-ms, 'title')]", container, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (titleElement && isValidTitle(titleElement.textContent.trim())) {{
                                    title = titleElement.textContent.trim();
                                }} else {{
                                    // Try finding an "h2" tag or similar header elements
                                    const headingElement = document.evaluate(".//h1|.//h2|.//h3|.//strong", container, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                    if (headingElement && isValidTitle(headingElement.textContent.trim())) {{
                                        title = headingElement.textContent.trim();
                                    }} else {{
                                        // Try the link's aria-label
                                        const linkLabel = linkElement.getAttribute('aria-label');
                                        if (linkLabel && isValidTitle(linkLabel)) {{
                                            title = linkLabel;
                                        }} else {{
                                            // Fall back to parsing container text line by line
                                            const lines = containerText.split('\\n').map(line => line.trim()).filter(Boolean);
                                            for (const line of lines) {{
                                                if (!line.match(/(?:CA\\$|£|\\$|€)[0-9,.]+/) && isValidTitle(line)) {{
                                                    title = line;
                                                    break;
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                                
                                // Try extracting from meta tags as last resort
                                if (title === "Unknown Title") {{
                                    const metaDesc = document.querySelector('meta[property="og:description"]');
                                    if (metaDesc && metaDesc.content) {{
                                        const descContent = metaDesc.content;
                                        const possibleTitle = descContent.split(' - ')[0];
                                        if (isValidTitle(possibleTitle)) {{
                                            title = possibleTitle;
                                        }}
                                    }}
                                }}
                                
                                results.push({{
                                    id,
                                    title,
                                    price,
                                    url
                                }});
                            }}
                            
                            return results;
                        }}
                    """, strategy)
                    
                    if listing_data and len(listing_data) > 0:
                        results.extend(listing_data)
                        break
            
            return results
            
        except Exception as e:
            logging.warning(f"Error extracting listings via XPath: {e}")
            return []
    
    async def extract_via_multiple_strategies(self):
        results = []
        
        try:
            logging.info("Trying XPath extraction strategy...")
            xpath_results = await self.extract_listings_via_xpath()
            if xpath_results:
                logging.info(f"Found {len(xpath_results)} listings via XPath")
                results.extend(xpath_results)
        except Exception as e:
            logging.warning(f"XPath extraction failed: {e}")
        
        if not results:
            try:
                logging.info("Trying JavaScript extraction strategy...")
                js_results = await self.extract_listings_via_javascript()
                if js_results:
                    logging.info(f"Found {len(js_results)} listings via JavaScript")
                    results.extend(js_results)
            except Exception as e:
                logging.warning(f"JavaScript extraction failed: {e}")
        
        # Filter out any results with generic titles
        filtered_results = []
        seen_urls = set()
        
        for result in results:
            if result['url'] in seen_urls:
                continue
                
            if result['title'] in ['Log In', 'Marketplace', 'Unknown Title']:
                continue
                
            seen_urls.add(result['url'])
            filtered_results.append(result)
        
        return filtered_results
    
    async def search_marketplace(self):
        results = []
        try:
            search_url = self._build_search_url()
            logging.info(f"Navigating to: {search_url}")
            
            await self.page.goto(search_url, wait_until="domcontentloaded")
            await self.random_wait(reason="after initial page load")
            
            await self.handle_initial_dialogs()
            
            for attempt in range(3):
                try:
                    await self.simulate_human_behavior()
                    
                    results = await self.extract_via_multiple_strategies()
                    
                    if results:
                        logging.info(f"Successfully extracted {len(results)} unique listings on attempt {attempt+1}")
                        break
                    else:
                        logging.warning(f"No results found on attempt {attempt+1}, retrying...")
                        await self.random_wait(3, 5, "before retry")
                except Exception as e:
                    logging.warning(f"Error during extraction attempt {attempt+1}: {e}")
                    await self.random_wait(3, 5, "after error")
            
            if not results:
                await self.page.screenshot(path="no_results.png")
                logging.error("All extraction attempts failed")
                
                # Last resort: try to at least get the links
                try:
                    links = await self.page.evaluate("""
                        () => {
                            return Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'))
                                .map(a => a.href)
                                .filter((v, i, a) => a.indexOf(v) === i);
                        }
                    """)
                    
                    if links:
                        logging.info(f"Found {len(links)} marketplace links as last resort")
                        for url in links[:10]:
                            id_match = re.search(r'/item/([^/\?]+)', url)
                            id = id_match.group(1) if id_match else "unknown"
                            results.append({
                                "id": id,
                                "title": "Unknown Product",
                                "price": 0,
                                "url": url
                            })
                except Exception as e:
                    logging.error(f"Failed to extract links as last resort: {e}")
            
            return results[:10]  # Limit to 10 results
            
        except TimeoutError as e:
            logging.error(f"Timeout during marketplace search: {e}")
            await self.page.screenshot(path="timeout_error.png")
            return []
        except Exception as e:
            logging.error(f"Error during marketplace search: {e}")
            await self.page.screenshot(path="error.png")
            self.config.set_active(False)
            return []
    
    async def run_search(self):
        if not self.config.is_active():
            logging.info("Search is not active. Skipping.")
            return []
        
        try:
            await self.initialize()
            results = await self.search_marketplace()
            return results
        finally:
            await self.close()

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