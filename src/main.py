import asyncio
import logging
import os
import sys
import random
import time
from datetime import datetime, timedelta
import configparser
import sqlite3
import threading
import queue

from scraper import MarketplaceScraper
from notifier import EmailNotifier


class ConfigManager:
    def __init__(self, config_path="search_config.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        self.config.read(self.config_path)
        if 'Search' not in self.config:
            raise ValueError("Config file missing [Search] section")
    
    def get_search_params(self):
        params = {}
        for key, value in self.config['Search'].items():
            if key != 'active' and key != 'frequency' and key != 'email' and not key.endswith('_template'):
                params[key] = value
        return params
    
    def get_email_config(self):
        email_config = {
            'recipient_email': self.config['Search'].get('email', ''),
            'subject_template': self.config['Search'].get('subject_template', 'Found: {item_title} at ${price}'),
            'message_template': self.config['Search'].get('message_template', 'Found a {item_title} selling for ${price} in {location}. Here\'s the link: {url}')
        }
        return email_config
    
    def get_frequency(self):
        return int(self.config['Search'].get('frequency', 15))
    
    def is_active(self):
        return self.config['Search'].getboolean('active', False)
    
    def set_active(self, active_state):
        self.config['Search']['active'] = str(active_state)
        with open(self.config_path, 'w') as config_file:
            self.config.write(config_file)


class DatabaseManager:
    def __init__(self, db_path="marketplace_scraper.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.initialize()
        
    def initialize(self):
        db_exists = os.path.exists(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        if not db_exists:
            self.create_tables()
            logging.info(f"Database created at {self.db_path}")
        
    def create_tables(self):
        self.cursor.execute('''
        CREATE TABLE listings (
            id TEXT PRIMARY KEY,
            title TEXT,
            price REAL,
            url TEXT,
            location TEXT,
            discovered_at TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP,
            search_terms TEXT,
            items_found INTEGER,
            new_items INTEGER,
            status TEXT
        )
        ''')
        
        self.conn.commit()
        
    def item_exists(self, item_id):
        self.cursor.execute("SELECT id FROM listings WHERE id = ?", (item_id,))
        return self.cursor.fetchone() is not None
        
    def add_item(self, item_id, title, price, url, location="Unknown"):
        try:
            self.cursor.execute(
                "INSERT INTO listings VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, title, price, url, location, datetime.now())
            )
            self.conn.commit()
            logging.info(f"Added new item to database: {title} (${price})")
            return True
        except sqlite3.Error as e:
            logging.error(f"Database error when adding item: {e}")
            return False
            
    def log_search(self, search_terms, items_found, new_items, status="completed"):
        try:
            self.cursor.execute(
                "INSERT INTO searches (timestamp, search_terms, items_found, new_items, status) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(), search_terms, items_found, new_items, status)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Database error when logging search: {e}")
            return False
    
    def get_recent_searches(self, limit=5):
        self.cursor.execute(
            "SELECT timestamp, search_terms, items_found, new_items, status FROM searches ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        )
        return self.cursor.fetchall()
        
    def close(self):
        if self.conn:
            self.conn.close()


class SimpleTerminalInterface:
    def __init__(self):
        self.status = "Initializing..."
        self.next_run_time = None
        self.command_queue = queue.Queue()
        self.running = True
        self.force_run_requested = False
        self._setup_input_thread()
        
    def _setup_input_thread(self):
        self.input_thread = threading.Thread(target=self._input_listener)
        self.input_thread.daemon = True
        self.input_thread.start()
    
    def _is_data_available(self):
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
    
    def _getch(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
        
    def _input_listener(self):
        while self.running:
            if self._is_data_available():
                key = self._getch()
                if key == 'f':
                    print("\nForce a run now? (y/n): ", end='', flush=True)
                    confirm = self._getch()
                    print(confirm)
                    if confirm.lower() == 'y':
                        self.force_run_requested = True
                        self.command_queue.put("force_run")
                        print("Run forced!")
                    else:
                        print("Run cancelled.")
                elif key == 'q':
                    print("\nQuit? (y/n): ", end='', flush=True)
                    confirm = self._getch()
                    print(confirm)
                    if confirm.lower() == 'y':
                        self.running = False
                        self.command_queue.put("quit")
                        print("Shutting down...")
                    else:
                        print("Quit cancelled.")
                # Clear the input buffer
                while self._is_data_available():
                    self._getch()
            time.sleep(0.1)
    
    def display_status(self):
        os.system('clear' if os.name == 'posix' else 'cls')
        print("\n" + "=" * 60)
        print(f"FACEBOOK MARKETPLACE SCRAPER")
        print("=" * 60)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nCurrent Time: {current_time}")
        
        print(f"\nStatus: {self.status}")
        
        if self.next_run_time:
            time_remaining = self.next_run_time - datetime.now()
            if time_remaining.total_seconds() > 0:
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                print(f"Next Run: {self.next_run_time.strftime('%H:%M:%S')} (in {minutes}m {seconds}s)")
            else:
                print("Next Run: Imminent")
        
        print("\nCommands:")
        print("  f - Force a run now")
        print("  q - Quit application")
        print("\n" + "-" * 60)
    
    def update_status(self, status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status = f"{timestamp} | {status}"
        print(f"\n{self.status}")
        logging.info(status)
        self.display_status()
    
    def set_next_run_time(self, next_time):
        self.next_run_time = next_time
        self.display_status()
    
    def check_for_force_run(self):
        if self.force_run_requested:
            self.force_run_requested = False
            return True
        return False
    
    def get_command(self):
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None
    
    def start(self):
        self.display_status()
    
    def stop(self):
        self.running = False
        if hasattr(self, 'input_thread'):
            self.input_thread.join(timeout=1.0)


class MarketplaceApp:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("marketplace_scraper.log"),
                logging.StreamHandler()
            ]
        )
        
        try:
            self.config = ConfigManager()
            self.db = DatabaseManager()
            self.email = EmailNotifier(self.config.get_email_config())
            self.terminal = SimpleTerminalInterface()
            self.scraper = MarketplaceScraper(self.config)
            
            self.next_run_time = datetime.now()
            self.running = True
            
            logging.info("Application initialized successfully")
        except Exception as e:
            logging.critical(f"Failed to initialize application: {e}")
            sys.exit(1)
    
    def calculate_next_run_time(self):
        base_minutes = self.config.get_frequency()
        random_minutes = random.uniform(0, 5)
        total_minutes = base_minutes + random_minutes
        
        next_run = datetime.now() + timedelta(minutes=total_minutes)
        logging.info(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (base: {base_minutes}m + random: {random_minutes:.2f}m)")
        
        return next_run
    
    async def process_search_results(self, results):
        if not results:
            logging.info("No results found in this search")
            return 0
        
        new_items = 0
        for item in results:
            item_id = item.get('id', 'unknown')
            
            if not self.db.item_exists(item_id):
                self.db.add_item(
                    item_id,
                    item.get('title', 'Unknown Title'),
                    item.get('price', 0),
                    item.get('url', ''),
                    item.get('location', 'Unknown location')
                )
                
                self.email.send_item_notification(item)
                new_items += 1
        
        logging.info(f"Found {len(results)} items, {new_items} new")
        self.db.log_search(
            self.config.get_search_params().get('keywords', ''),
            len(results),
            new_items
        )
        
        return new_items
    
    async def run_search_cycle(self):
        if not self.config.is_active():
            self.terminal.update_status("Search is not active. Waiting...")
            return False
        
        try:
            self.terminal.update_status("Browsing marketplace...")
            results = await self.scraper.run_search()
            new_items = await self.process_search_results(results)
            
            self.terminal.update_status(f"Search completed, found {len(results)} items ({new_items} new)")
            return True
            
        except Exception as e:
            error_msg = f"Error during search cycle: {e}"
            logging.error(error_msg)
            self.email.send_error_notification(error_msg)
            self.config.set_active(False)
            self.terminal.update_status(f"ERROR: {str(e)}")
            return False
    
    async def main_loop(self):
        self.terminal.start()
        self.terminal.update_status("Application started")
        
        while self.running:
            current_time = datetime.now()
            
            if self.terminal.check_for_force_run() or current_time >= self.next_run_time:
                await self.run_search_cycle()
                self.next_run_time = self.calculate_next_run_time()
                self.terminal.set_next_run_time(self.next_run_time)
            
            command = self.terminal.get_command()
            if command == "quit":
                self.running = False
                self.terminal.update_status("Shutting down...")
                break
            
            await asyncio.sleep(1)
    
    async def run(self):
        try:
            await self.main_loop()
        finally:
            self.terminal.stop()
            self.db.close()
            logging.info("Application shut down")


if __name__ == "__main__":
    import select
    import termios
    import tty
    
    app = MarketplaceApp()
    asyncio.run(app.run())