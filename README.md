# Market Place Email Alert

A command-line tool that automatically searches Facebook Marketplace for items matching your criteria and sends email notifications when new listings are found.

## Features

- Scheduled automatic searches with configurable frequency
- Email notifications for new items
- Local database to track listings and avoid duplicates
- Simple terminal interface with keyboard commands
- Random timing between searches to avoid detection

## Setup

1. Install required dependencies:
   ```
   pip install playwright asyncio
   playwright install chromium
   ```

2. Configure your search parameters in `search_config.ini`:
   ```ini
   [Search]
   active = True
   keywords = your search terms
   min_price = 50
   max_price = 500
   location = City, Region
   search_radius = 25
   frequency = 15
   email = your.email@example.com
   subject_template = Found: {item_title} at ${price}
   message_template = Found a {item_title} selling for ${price} in {location}. \nHere's the link: {url}
   ```

3. Create a `password.ini` file with your email credentials:
   ```ini
   [Email]
   sender_email = your.sender.email@gmail.com
   sender_password = your-app-password
   ```
   Note: For Gmail, you need to use an App Password, not your regular password.

## Usage

Start the scraper:
```
python main.py
```

### Commands
- Press `f` to force a search run immediately
- Press `q` to quit the application

## Files

- `main.py` - Main application logic
- `scraper.py` - Handles marketplace browsing with Playwright
- `extraction.py` - Extracts listing data from marketplace pages
- `notifier.py` - Sends email notifications
- `browser.py` - Manages browser automation
- `database.py` - Tracks listings and search history

## Notes

- The scraper uses a headless browser to simulate human browsing behavior
- Email notifications require valid SMTP settings
- Search frequency is randomized slightly to avoid detection