import logging

class ExtractionManager:
    def __init__(self, page):
        self.page = page
    
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
                        if (!line.match(/(?:CA\\$|£|\\$|€)[0-9,.]+/)) {
                            if (line.length > 3) return line;
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
                            
                            const containers = [];
                            const elements = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                            for (let i = 0; i < elements.snapshotLength; i++) {{
                                containers.push(elements.snapshotItem(i));
                            }}
                            
                            for (const container of containers) {{
                                // Find the link to the item
                                const linkElement = document.evaluate(".//a[contains(@href, '/marketplace/item/')]", container, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (!linkElement) continue;
                                
                                const url = linkElement.href;
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
                                if (titleElement) {{
                                    title = titleElement.textContent.trim();
                                }} else {{
                                    // Try the link's aria-label
                                    const linkLabel = linkElement.getAttribute('aria-label');
                                    if (linkLabel && linkLabel.length > 3) {{
                                        title = linkLabel;
                                    }} else {{
                                        // Fall back to parsing container text
                                        const lines = containerText.split('\\n').map(line => line.trim()).filter(Boolean);
                                        for (const line of lines) {{
                                            if (!line.match(/(?:CA\\$|£|\\$|€)[0-9,.]+/)) {{
                                                if (line.length > 3) {{
                                                    title = line;
                                                    break;
                                                }}
                                            }}
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
        
        return results