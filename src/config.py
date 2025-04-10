import configparser
import os
import sys
import logging

class ConfigManager:
    def __init__(self, config_path="search_config.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.load_config()
        
    def load_config(self):
        if not os.path.exists(self.config_path):
            logging.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
            
        try:
            self.config.read(self.config_path)
            self._validate_config()
        except Exception as e:
            logging.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
    
    def _validate_config(self):
        required_fields = [
            ('Search', 'active'),
            ('Search', 'keywords'),
            ('Search', 'min_price'),
            ('Search', 'max_price'),
            ('Search', 'location'),
            ('Search', 'search_radius'),
            ('Search', 'frequency'),
            ('Search', 'email'),
            ('Search', 'subject_template'),
            ('Search', 'message_template')
        ]
        
        for section, field in required_fields:
            if not self.config.has_section(section) or not self.config.has_option(section, field):
                logging.error(f"Missing required configuration: [{section}] {field}")
                sys.exit(1)
    
    def is_active(self):
        return self.config.getboolean('Search', 'active')
    
    def set_active(self, active_status):
        self.config.set('Search', 'active', str(active_status))
        with open(self.config_path, 'w') as f:
            self.config.write(f)
    
    def get_search_params(self):
        return {
            'keywords': self.config.get('Search', 'keywords'),
            'min_price': self.config.getfloat('Search', 'min_price'),
            'max_price': self.config.getfloat('Search', 'max_price'),
            'location': self.config.get('Search', 'location'),
            'search_radius': self.config.getint('Search', 'search_radius'),
            'frequency': self.config.getint('Search', 'frequency')
        }
    
    def get_notification_params(self):
        return {
            'email': self.config.get('Search', 'email'),
            'subject_template': self.config.get('Search', 'subject_template'),
            'message_template': self.config.get('Search', 'message_template')
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = ConfigManager()
    print("Configuration loaded successfully.")
    print(f"Active: {manager.is_active()}")
    print(f"Search parameters: {manager.get_search_params()}")
    print(f"Notification parameters: {manager.get_notification_params()}")