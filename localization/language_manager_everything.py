import os
import json
from typing import Dict, Optional

class LanguageManagerEverything:
    def __init__(self, initial_language: str = "English"):
        """Initialize the language manager with initial language"""
        self.strings = {}
        self.tooltips = {}
        self.current_language = None
        self.language_codes = {}
        self._load_languages()
        
        # Set initial language, defaulting to English if specified language not found
        if initial_language in self.get_languages():
            self.set_language(initial_language)
        else:
            self.set_language("English")

    def _load_languages(self):
        """Load available language files and their codes"""
        localization_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load all language files
        for file in os.listdir(localization_dir):
            if file.startswith('everything-') and file.endswith('.json'):
                # Remove 'everything-' prefix and '.json' extension
                lang_code = file[len('everything-'):-5]
                with open(os.path.join(localization_dir, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "language" in data and "name" in data["language"]:
                        lang_name = data["language"]["name"]
                        self.language_codes[lang_name] = lang_code

    def set_language(self, language: str) -> bool:
        """Set the current language and load its strings"""
        if language in self.get_languages():
            self.current_language = language
            lang_code = self.language_codes.get(language, language)
            lang_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"everything-{lang_code}.json")
            
            if os.path.exists(lang_file):
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.strings = data
                    self.tooltips = data.get("tooltips", {})
                    return True
            else:
                raise FileNotFoundError(f"Language file missing: {lang_file}")
        return False

    def get_languages(self) -> list:
        """Get list of available languages"""
        return list(self.language_codes.keys())

    def get_string(self, key: str, *args) -> str:
        """Get a localized string by key with optional format arguments"""
        if not key:
            return key
            
        # Split the key by dots to traverse nested dictionaries
        keys = key.split('.')
        value = self.strings
        
        # Traverse the nested structure
        for k in keys:
            if isinstance(value, dict):
                if k in value:
                    value = value[k]
                else:
                    return key
            else:
                return key
        
        # If we found a dict instead of a string, check for 'text' key
        if isinstance(value, dict):
            if 'text' in value:
                value = value['text']
            else:
                return key
        
        # Format the string if arguments are provided
        if args and isinstance(value, str):
            try:
                return value.format(*args)
            except (IndexError, KeyError):
                return value
        
        if not isinstance(value, str):
            return key
            
        return value

    def get_tooltip(self, key: str) -> str:
        """Get a localized tooltip by key"""
        # First check in tooltips section
        tooltip = self.tooltips.get(key, "")
        if tooltip:
            if isinstance(tooltip, dict) and "text" in tooltip:
                tooltip = tooltip["text"]
            return tooltip if isinstance(tooltip, str) else ""
            
        # Then check if it's a checkbox with a tooltip
        checkbox_key = f"checkboxes.{key}.tooltip"
        value = self.get_string(checkbox_key)
        if value != checkbox_key:  # If we got a real value back
            return value
            
        return ""

    def get_language_code(self, language_name: str) -> str:
        """Get the language code for a language name"""
        return self.language_codes.get(language_name, language_name)

    def get_language_name(self, language_code: str) -> str:
        """Get the language name for a language code"""
        for name, code in self.language_codes.items():
            if code == language_code:
                return name
        return language_code 