import os
import configparser
from typing import Dict, Any

class ConfigManagerEverything:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config/config-everything.ini')
        
        # Set default values
        self.config['Interface'] = {
            'language': 'English'
        }
        self.config['Search'] = {
            'regex_filter': ''
        }
        self.config['Output'] = {
            'enable_logging': 'False',
            'match_folder_structure': 'True'
        }
        self.config['Paths'] = {
            'default_copy_folder': '',
            'default_move_folder': ''
        }
        
        # Load existing config if it exists
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
    
    def get(self, section, key, default=None):
        """Get a value from the config"""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def get_bool(self, section, key, default=False):
        """Get a boolean value from the config"""
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def set(self, section, key, value):
        """Set a value in the config"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
    
    def save_config(self):
        """Save the config to file"""
        # Ensure the config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Save to file
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        """Get all settings as a dictionary"""
        return {section: dict(self.config[section]) for section in self.config.sections()} 