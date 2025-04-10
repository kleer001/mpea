import asyncio
import logging
import random
from playwright.async_api import async_playwright, TimeoutError

class BrowserManager:
    def __init__(self, user_data_dir, storage_state_path):
        self.user_data_dir = user_data_dir
        self.storage_state_path = storage_state_path
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
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
            "viewport": {"width": 1920, "height": 1080},
            "geolocation": {"latitude": 49.2827, "longitude": -123.1207},  # Default Vancouver coordinates
            "permissions": ["geolocation"]
        }
        
        import os
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
    
    async def update_geolocation(self, latitude, longitude):
        await self.context.set_geolocation({"latitude": latitude, "longitude": longitude})
        logging.info(f"Updated geolocation to: {latitude}, {longitude}")
    
    async def verify_and_set_location(self, location_name):
        try:
            logging.info(f"Verifying location: {location_name}")
            
            # First check if current location matches expected location
            current_location = await self.get_current_location()
            logging.info(f"Current marketplace location: {current_location}")
            
            if current_location and location_name.lower() in current_location.lower():
                logging.info(f"Already searching in the correct location: {current_location}")
                return True
            
            # If not, try to set it manually
            logging.info(f"Current location doesn't match expected. Attempting to set location to: {location_name}")
            
            # Click on location selector
            try:
                # Try various selectors that might represent the location filter
                location_selectors = [
                    'button:has-text("Location")',
                    'button[aria-label="Location"]',
                    'input[placeholder="Location"]',
                    '[aria-label="Current location"]',
                    'button:has-text("Change location")',
                    '[role="button"]:has-text("Anywhere")',
                    'div[aria-haspopup="menu"]:has-text("Location")'
                ]
                
                for selector in location_selectors:
                    location_button = self.page.locator(selector)
                    if await location_button.count() > 0:
                        logging.info(f"Found location button with selector: {selector}")
                        await location_button.click()
                        await self.random_wait(2, 3, "after clicking location button")
                        break
                else:
                    logging.warning("Could not find location button with known selectors")
                    
                # Look for location input field
                location_input_selectors = [
                    'input[placeholder="Location"]',
                    'input[aria-label="Location"]',
                    'input[name="location"]',
                    'input[name="city"]',
                    'input[type="text"]'
                ]
                
                for selector in location_input_selectors:
                    location_input = self.page.locator(selector)
                    if await location_input.count() > 0:
                        logging.info(f"Found location input with selector: {selector}")
                        # Clear existing text
                        await location_input.fill("")
                        await self.random_wait(1, 2, "after clearing location input")
                        
                        # Type new location slowly
                        for char in location_name:
                            await location_input.type(char, delay=random.uniform(50, 150))
                            await asyncio.sleep(0.05)
                        
                        await self.random_wait(2, 3, "after typing location")
                        
                        # Press Enter to submit
                        await location_input.press("Enter")
                        await self.random_wait(3, 5, "after submitting location")
                        break
                else:
                    logging.warning("Could not find location input with known selectors")
                    return False
                
                # Verify location was set correctly
                new_location = await self.get_current_location()
                logging.info(f"New marketplace location: {new_location}")
                
                if new_location and location_name.lower() in new_location.lower():
                    logging.info(f"Successfully set location to: {new_location}")
                    return True
                else:
                    logging.warning(f"Failed to set location. Current location: {new_location}")
                    return False
                
            except Exception as e:
                logging.error(f"Error setting location: {e}")
                return False
                
        except Exception as e:
            logging.error(f"Error verifying location: {e}")
            return False
    
    async def get_current_location(self):
        try:
            # Multiple strategies to find the current location text
            location_text = await self.page.evaluate("""
                () => {
                    // Strategy 1: Look for location in page title
                    const title = document.title;
                    if (title.includes(" in ") || title.includes(" • ")) {
                        const parts = title.split(/( in | • )/);
                        if (parts.length > 1) return parts[2];
                    }
                    
                    // Strategy 2: Look for location pill/button
                    const locationPills = Array.from(document.querySelectorAll('[role="button"]')).filter(el => 
                        el.textContent && 
                        !el.textContent.includes("$") && 
                        !el.textContent.includes("Filter") &&
                        !el.textContent.includes("Sort") &&
                        !el.textContent.toLowerCase().includes("sale") &&
                        el.textContent.length > 3 &&
                        el.textContent.length < 50
                    );
                    
                    if (locationPills.length > 0) {
                        // Find the most likely location pill
                        for (const pill of locationPills) {
                            if (pill.textContent.includes(",") || 
                                pill.textContent.includes(" Area") ||
                                pill.textContent.includes("mile")) {
                                return pill.textContent.trim();
                            }
                        }
                        return locationPills[0].textContent.trim();
                    }
                    
                    // Strategy 3: Look for location in breadcrumbs
                    const breadcrumbs = Array.from(document.querySelectorAll('a[href*="/marketplace/"]'));
                    for (const crumb of breadcrumbs) {
                        if (crumb.href.includes("/marketplace/") && 
                            !crumb.href.includes("/marketplace/item/") &&
                            !crumb.href.includes("/marketplace/search")) {
                            return crumb.textContent.trim();
                        }
                    }
                    
                    return null;
                }
            """)
            
            return location_text
        except Exception as e:
            logging.warning(f"Error getting current location: {e}")
            return None
    
    async def close(self):
        if self.context:
            await self.save_session()
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()