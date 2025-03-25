import os
import sys
import argparse
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess
import json
from datetime import datetime
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing
from threading import Lock
import csv
import webbrowser
import winreg
import re
from localization.language_manager_everything import LanguageManagerEverything
from config.config_manager_everything import ConfigManagerEverything

EVERYTHING_DOWNLOAD_URL = "https://www.voidtools.com/downloads/"

def find_everything_installation():
    """Find Everything installation directory"""
    possible_paths = [
        r"C:\Program Files\Everything",
        r"C:\Program Files (x86)\Everything",
    ]
    
    # Try registry first
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Everything") as key:
            install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
            if install_location and os.path.exists(install_location):
                possible_paths.insert(0, install_location)
    except WindowsError:
        pass
    
    # Check each possible path
    for path in possible_paths:
        if os.path.exists(path):
            everything_exe = os.path.join(path, "Everything.exe")
            if os.path.exists(everything_exe):
                return path
    
    return None

def check_file_exists(path):
    """Check if a file exists and is executable"""
    if not os.path.exists(path):
        return False
    
    if not os.path.isfile(path):
        return False
    
    try:
        # Try to check if file is executable
        if os.access(path, os.X_OK):
            return True
        else:
            return False
    except Exception:
        return False

def run_es_exe(es_path):
    """Try to run es.exe and get version"""
    try:
        # Use full path if not in PATH
        cmd = [es_path, '-version']
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return False, None

def find_es_exe():
    """Find es.exe in various locations"""
    results = {
        'found': False,
        'path': None,
        'version': None,
        'error': None,
        'locations_checked': []
    }
    
    # First check PATH
    try:
        # Try to find es.exe in PATH
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        for dir in path_dirs:
            es_path = os.path.join(dir, 'es.exe')
            if os.path.exists(es_path):
                success, version = run_es_exe(es_path)
                if success:
                    results['found'] = True
                    results['path'] = es_path
                    results['version'] = version
                    return results
    except Exception as e:
        results['error'] = str(e)
    
    results['locations_checked'].append('System PATH')
    
    # Check Everything installation directory
    install_dir = find_everything_installation()
    if install_dir:
        es_path = os.path.join(install_dir, 'es.exe')
        results['locations_checked'].append(es_path)
        
        if check_file_exists(es_path):
            success, version = run_es_exe(es_path)
            if success:
                results['found'] = True
                results['path'] = es_path
                results['version'] = version
                return results
    
    # Check current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    es_path = os.path.join(current_dir, 'es.exe')
    results['locations_checked'].append(es_path)
    
    if check_file_exists(es_path):
        success, version = run_es_exe(es_path)
        if success:
            results['found'] = True
            results['path'] = es_path
            results['version'] = version
            return results
    
    return results

def check_everything_service():
    """Check if Everything service is running"""
    try:
        result = subprocess.run(['sc', 'query', 'Everything'], capture_output=True, text=True)
        return 'RUNNING' in result.stdout
    except Exception:
        return False

def check_everything_cli():
    """Check if Everything CLI (es.exe) is available"""
    # First check if service is running
    service_running = check_everything_service()
    
    # Then check for es.exe
    results = find_es_exe()
    
    return results['found']

def check_everything_status():
    """Check if Everything is installed, running and ready"""
    try:
        # Check service
        service_result = subprocess.run(['sc', 'query', 'Everything'], capture_output=True, text=True)
        if 'RUNNING' not in service_result.stdout:
            return False, "Everything service is not running"
            
        # Check if es.exe exists and works
        result = subprocess.run(['es.exe', '-get-everything-version'], capture_output=True, text=True)
        if result.returncode != 0:
            return False, "Everything CLI (es.exe) not found"
            
        # Check if still indexing
        result = subprocess.run(['es.exe', '-get-result-count', 'ext:'], capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            return False, "Everything is still indexing files"
            
        return True, None
    except FileNotFoundError:
        return False, "Everything CLI (es.exe) not found"
    except Exception as e:
        return False, str(e)

def show_everything_instructions():
    """Show instructions for installing Everything and es.exe"""
    message = """Everything search engine is required!

1. Download and install Everything (not Everything Lite):
   - https://www.voidtools.com/downloads/
   - Make sure to select "Install Everything Service" and "CLI"
   - Restart your computer after installation

2. Wait for Everything to finish indexing your files
   (this might take a few minutes)

Would you like to open the download page?"""

    if messagebox.askyesno("Everything Required", message):
        webbrowser.open(EVERYTHING_DOWNLOAD_URL)
    return False

def search_single_file(filename, regex_pattern=None):
    """Search for a single file using Everything CLI"""
    try:
        # Use the filename as is, without forcing any extension
        search_term = filename
        
        # Use -full-path-and-name to get absolute paths
        cmd = ['es.exe', '-full-path-and-name', search_term]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            
            # Apply regex filter if provided
            if regex_pattern:
                try:
                    regex = re.compile(regex_pattern)
                    paths = [path for path in paths if regex.search(path)]
                except re.error:
                    return []
            
            return [(filename, path) for path in paths]
        return []
    except Exception:
        return []

class EverythingSearcher:
    def __init__(self, input_file=None, input_text=None, copy_path=None, move_path=None, log_path=None, 
                 match_folder_structure=True, delete_mode=False, log_callback=None, progress_callback=None,
                 regex_filter=None, lang=None):
        self.input_file = input_file
        self.input_text = input_text
        self.copy_path = copy_path
        self.move_path = move_path
        self.log_path = log_path
        self.match_folder_structure = match_folder_structure
        self.delete_mode = delete_mode
        self.regex_filter = regex_filter
        self.lang = lang  # Store language manager
        
        # Store callbacks but don't pickle them
        self._log_callback = log_callback
        self._progress_callback = progress_callback
        
        # Results tracking
        self.found_files = []
        self.processed_files = []
        self.failed_files = []
        
        # Create necessary directories
        if self.log_path:
            os.makedirs(self.log_path, exist_ok=True)
        if self.copy_path:
            os.makedirs(self.copy_path, exist_ok=True)
        if self.move_path:
            os.makedirs(self.move_path, exist_ok=True)
    
    def __getstate__(self):
        """Remove callbacks when pickling"""
        state = self.__dict__.copy()
        state['_log_callback'] = None
        state['_progress_callback'] = None
        return state
    
    def __setstate__(self, state):
        """Restore state after unpickling"""
        self.__dict__.update(state)

    def log(self, message):
        """Log a message"""
        print(message)
        if self._log_callback:
            try:
                self._log_callback(message)
            except Exception as e:
                print(f"Error in log callback: {str(e)}")
        if self.log_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.log_path, f"log_{timestamp}.txt")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()}: {message}\n")

    def update_progress(self, phase, current, total):
        """Update progress through callback if set"""
        if self._progress_callback:
            try:
                self._progress_callback(phase, current, total)
            except Exception as e:
                print(f"Error in progress callback: {str(e)}")

    def read_input_file(self):
        """Read filenames from input file or text"""
        if self.input_text:
            return [line.strip() for line in self.input_text.splitlines() if line.strip()]
            
        if not self.input_file:
            return []
            
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.log(f"Error reading input file: {str(e)}")
            return []

    def process_file(self, file_info):
        """Process a single found file"""
        filename, source_path = file_info
        
        try:
            if self.delete_mode:
                os.remove(source_path)
                return True
            
            if self.copy_path:
                if self.match_folder_structure:
                    rel_path = os.path.splitdrive(source_path)[1].lstrip(os.sep)
                    dest_dir = os.path.join(self.copy_path, rel_path)
                    os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
                    shutil.copy2(source_path, dest_dir)
                else:
                    dest = os.path.join(self.copy_path, filename)
                    shutil.copy2(source_path, dest)
            
            if self.move_path:
                if self.match_folder_structure:
                    rel_path = os.path.splitdrive(source_path)[1].lstrip(os.sep)
                    dest_dir = os.path.join(self.move_path, rel_path)
                    os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
                    shutil.move(source_path, dest_dir)
                else:
                    dest = os.path.join(self.move_path, filename)
                    shutil.move(source_path, dest)
            
            return True
        except Exception as e:
            self.log(f"Error processing {source_path}: {str(e)}")
            return False

    def process_files(self):
        """Main processing function"""
        # Read input files
        filenames = self.read_input_file()
        if not filenames:
            self.log(self.lang.get_string("messages.no_files"))
            return
            
        self.log(self.lang.get_string("messages.processing").format(len(filenames)))
        self.log("\n" + self.lang.get_string("messages.searching"))
        for filename in filenames:
            self.log(f"- {filename}")
        
        # Validate regex pattern if provided
        if self.regex_filter:
            try:
                re.compile(self.regex_filter)
            except re.error as e:
                self.log(self.lang.get_string("errors.invalid_regex").format(str(e)))
                return
        
        # Search for files
        total_files = len(filenames)
        processed_files = 0
        found_count = 0
        
        # Search for files
        with ProcessPoolExecutor(max_workers=max(1, multiprocessing.cpu_count() - 1)) as executor:
            search_futures = [executor.submit(search_single_file, filename, self.regex_filter) 
                            for filename in filenames]
            
            for future in tqdm(as_completed(search_futures), total=len(search_futures),
                             desc="Searching files", unit="file"):
                processed_files += 1
                results = future.result()
                if results:
                    found_count += len(results)
                    self.found_files.extend(results)
                self.update_progress("search", processed_files, total_files)
        
        # Show found files
        if self.found_files:
            self.log("\n" + self.lang.get_string("messages.found_files"))
            for _, full_path in self.found_files:
                self.log(f"{full_path}")
        else:
            self.log("\n" + self.lang.get_string("messages.no_matches"))
            return
        
        # Process found files if any action is required
        if self.found_files:
            if self.delete_mode:
                # If delete mode is enabled, only delete files
                with ProcessPoolExecutor(max_workers=max(1, multiprocessing.cpu_count() - 1)) as executor:
                    process_futures = [executor.submit(self.process_file, file_info) 
                                     for file_info in self.found_files]
                    
                    processed_count = 0
                    for future in tqdm(as_completed(process_futures), total=len(process_futures),
                                     desc="Deleting files", unit="file"):
                        processed_count += 1
                        if future.result():
                            self.processed_files.append(self.found_files[processed_count - 1])
                        else:
                            self.failed_files.append(self.found_files[processed_count - 1])
                        self.update_progress("delete", processed_count, len(self.found_files))
            elif self.copy_path or self.move_path:
                # Only copy/move if delete mode is not enabled
                with ProcessPoolExecutor(max_workers=max(1, multiprocessing.cpu_count() - 1)) as executor:
                    process_futures = [executor.submit(self.process_file, file_info) 
                                     for file_info in self.found_files]
                    
                    processed_count = 0
                    for future in tqdm(as_completed(process_futures), total=len(process_futures),
                                     desc="Processing files", unit="file"):
                        processed_count += 1
                        if future.result():
                            self.processed_files.append(self.found_files[processed_count - 1])
                        else:
                            self.failed_files.append(self.found_files[processed_count - 1])
                        self.update_progress("process", processed_count, len(self.found_files))
        
        # Output summary
        self.log("\n" + self.lang.get_string("messages.summary"))
        self.log(self.lang.get_string("messages.total_processed").format(total_files))
        self.log(self.lang.get_string("messages.total_found").format(found_count))
        self.log(self.lang.get_string("messages.success_processed").format(len(self.processed_files)))
        if self.failed_files:
            self.log(self.lang.get_string("messages.failed_operations").format(len(self.failed_files)))
        
        actions = []
        if self.log_path:
            actions.append(self.lang.get_string("messages.logged_files"))
        if self.copy_path:
            actions.append(self.lang.get_string("messages.copied_files").format(len(self.processed_files)))
        if self.move_path:
            actions.append(self.lang.get_string("messages.moved_files").format(len(self.processed_files)))
        if self.delete_mode:
            actions.append(self.lang.get_string("messages.deleted_files").format(len(self.processed_files)))
            
        if actions:
            self.log(self.lang.get_string("messages.actions_taken").format(", ".join(actions)))

class SearchGUI:
    def __init__(self):
        self.root = tk.Tk()
        
        # Initialize config manager
        self.config = ConfigManagerEverything()
        
        # Initialize language manager
        initial_language = self.config.get("Interface", "language", "English")
        self.lang = LanguageManagerEverything(initial_language)
        self._initial_language = initial_language  # Store initial language
        
        # Verify language loading
        if not self.lang.current_language:
            print(f"Failed to load initial language: {initial_language}")
            print("Falling back to English")
            self.lang.set_language("English")
            if not self.lang.current_language:
                print("Failed to load English language!")
                self.root.destroy()
                return
        
        self.root.title(self.lang.get_string("window.title"))
        self.root.geometry("800x800")
        
        # Check if Everything is ready
        ready, error = check_everything_status()
        if not ready:
            messagebox.showerror("Error", error)
            if not show_everything_instructions():
                self.root.destroy()
                return
        
        # Configure style for centered combobox
        style = ttk.Style()
        style.configure('Centered.TCombobox', justify='center')
        
        # Create menu bar
        self.create_menu_bar()
        
        # Setup GUI components
        self.setup_gui()
        
        # Load saved settings
        self._load_settings()
        
        # Save settings on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def create_menu_bar(self):
        """Create the menu bar"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        # Language menu
        self.language_menu = tk.Menu(self.menubar, tearoff=0)
        menu_label = self.lang.get_string("menu.language")
        self.menubar.add_cascade(label=menu_label, menu=self.language_menu)
        
        # Add language options
        self.current_language = tk.StringVar(value=self.lang.current_language)
        
        # Get available languages
        languages = self.lang.get_languages()
        
        # Add English first if available
        if "English" in languages:
            self.language_menu.add_radiobutton(
                label="English",
                value="English",
                variable=self.current_language,
                command=self._on_language_change
            )
            self.language_menu.add_separator()
            languages.remove("English")
        
        # Add other languages in alphabetical order
        for lang in sorted(languages):
            self.language_menu.add_radiobutton(
                label=lang,
                value=lang,
                variable=self.current_language,
                command=self._on_language_change
            )
        
        # Store the mapping for later use
        self.language_codes = {lang: self.lang.get_language_code(lang) for lang in self.lang.get_languages()}

    def setup_gui(self):
        """Setup the GUI components"""
        # Configure root window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create and configure main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.columnconfigure(0, weight=1)
        
        # Input label and frame
        input_label = ttk.Label(self.main_frame, text=self.lang.get_string("labels.input_files"))
        input_label.string_key = "labels.input_files"
        input_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self._add_tooltip(input_label, "input_files")
        
        # Input frame
        input_frame = ttk.Frame(self.main_frame)
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        input_frame.columnconfigure(0, weight=1)
        
        # Input text area
        self.input_text = scrolledtext.ScrolledText(input_frame, height=10, wrap=tk.WORD)
        self.input_text.string_key = "input.default_text"
        self.input_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Store default text and bind focus events
        self.input_text.default_text = self.lang.get_string("input.default_text")
        self.input_text.default_color = "gray"
        self.input_text.normal_color = self.input_text.cget("fg")
        self.input_text.bind('<FocusIn>', self.on_input_focus_in)
        self.input_text.bind('<FocusOut>', self.on_input_focus_out)
        
        # Set initial state
        self.on_input_focus_out(None)
        
        # Options frame
        options_frame = ttk.LabelFrame(self.main_frame, text=self.lang.get_string("frames.options"))
        options_frame.string_key = "frames.options"
        options_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        options_frame.columnconfigure(1, weight=1)
        
        # Checkboxes frame
        checkbox_frame = ttk.Frame(options_frame)
        checkbox_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Operation options
        self.log_enabled = tk.BooleanVar(value=False)
        log_cb = ttk.Checkbutton(checkbox_frame, text=self.lang.get_string("checkboxes.logging.text"),
                                variable=self.log_enabled)
        log_cb.string_key = "checkboxes.logging.text"
        log_cb.grid(row=0, column=0, sticky=tk.W, padx=5)
        self._add_tooltip(log_cb, "logging")
        
        self.match_folder_structure = tk.BooleanVar(value=True)
        match_cb = ttk.Checkbutton(checkbox_frame, text=self.lang.get_string("checkboxes.match_structure.text"),
                                  variable=self.match_folder_structure)
        match_cb.string_key = "checkboxes.match_structure.text"
        match_cb.grid(row=0, column=1, sticky=tk.W, padx=5)
        self._add_tooltip(match_cb, "match_structure")
        
        self.delete_mode = tk.BooleanVar(value=False)
        delete_cb = ttk.Checkbutton(checkbox_frame, text=self.lang.get_string("checkboxes.delete_mode.text"),
                                   variable=self.delete_mode)
        delete_cb.string_key = "checkboxes.delete_mode.text"
        delete_cb.grid(row=0, column=2, sticky=tk.W, padx=5)
        self._add_tooltip(delete_cb, "delete_mode")
        
        # Copy/Move options
        copy_label = ttk.Label(options_frame, text=self.lang.get_string("labels.copy_to"), width=20, anchor='e')
        copy_label.string_key = "labels.copy_to"
        copy_label.grid(row=1, column=0, sticky=tk.W, pady=2)
        self._add_tooltip(copy_label, "copy_to")
        
        self.copy_path = tk.StringVar(value=self.config.get("Paths", "default_copy_folder", ""))
        copy_entry = ttk.Entry(options_frame, textvariable=self.copy_path)
        copy_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        copy_button = ttk.Button(options_frame, text=self.lang.get_string("buttons.browse"),
                               command=lambda: self.browse_output("copy"), width=20)
        copy_button.string_key = "buttons.browse"
        copy_button.grid(row=1, column=2, padx=5)
        
        move_label = ttk.Label(options_frame, text=self.lang.get_string("labels.move_to"), width=20, anchor='e')
        move_label.string_key = "labels.move_to"
        move_label.grid(row=2, column=0, sticky=tk.W, pady=2)
        self._add_tooltip(move_label, "move_to")
        
        self.move_path = tk.StringVar(value=self.config.get("Paths", "default_move_folder", ""))
        move_entry = ttk.Entry(options_frame, textvariable=self.move_path)
        move_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        move_button = ttk.Button(options_frame, text=self.lang.get_string("buttons.browse"),
                               command=lambda: self.browse_output("move"), width=20)
        move_button.string_key = "buttons.browse"
        move_button.grid(row=2, column=2, padx=5)
        
        # Add regex filter field
        regex_label = ttk.Label(options_frame, text=self.lang.get_string("labels.regex_filter"), width=20, anchor='e')
        regex_label.string_key = "labels.regex_filter"
        regex_label.grid(row=3, column=0, sticky=tk.W, pady=2)
        self._add_tooltip(regex_label, "regex_filter")
        
        self.regex_filter = tk.StringVar()
        regex_entry = ttk.Entry(options_frame, textvariable=self.regex_filter)
        regex_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # Process button
        self.process_button = ttk.Button(self.main_frame, text=self.lang.get_string("buttons.process"),
                                       command=self.start_processing, width=30)
        self.process_button.string_key = "buttons.process"
        self.process_button.grid(row=4, column=0, columnspan=4, pady=10, padx=10)
        # Add internal padding to make button taller
        self.process_button.configure(padding=(10, 5))
        
        # Progress frame
        progress_frame = ttk.LabelFrame(self.main_frame, text=self.lang.get_string("frames.progress"))
        progress_frame.string_key = "frames.progress"
        progress_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', variable=self.progress_var)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text=self.lang.get_string("progress.ready"))
        self.progress_label.string_key = "progress.ready"
        self.progress_label.grid(row=1, column=0, sticky=tk.W, padx=5)
        
        # Output text area
        self.log_output = scrolledtext.ScrolledText(self.main_frame, height=15)
        self.log_output.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Configure grid weights for main frame
        self.main_frame.rowconfigure(6, weight=1)  # Make log output expandable

    def update_progress(self, phase, current, total):
        """Update progress bar and label"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            phase_text = self.lang.get_string(f"progress.{phase}")
            self.progress_label.config(text=f"{phase_text}: {current}/{total} ({progress:.1f}%)")
        self.root.update_idletasks()

    def log_output(self, message):
        """Log a message to the output text area"""
        self.log_output.insert(tk.END, message + "\n")
        self.log_output.see(tk.END)
        self.root.update_idletasks()

    def start_processing(self):
        """Start the processing operation"""
        # Get input text
        input_text = self.input_text.get('1.0', tk.END).strip()
        if not input_text or input_text == self.input_text.default_text:
            messagebox.showerror("Error", self.lang.get_string("errors.no_files"))
            return
        
        # Check for dangerous operations and get confirmation
        if self.delete_mode.get():
            if not self._confirm_action("delete"):
                return
        elif self.move_path.get():
            if not self._confirm_action("move"):
                return
        
        # Validate regex pattern if provided
        regex_pattern = self.regex_filter.get().strip()
        if regex_pattern:
            try:
                re.compile(regex_pattern)
            except re.error as e:
                messagebox.showerror("Error", self.lang.get_string("errors.invalid_regex").format(str(e)))
                return
        
        # Disable process button
        self.process_button.state(['disabled'])
        self.progress_var.set(0)
        self.progress_label.config(text=self.lang.get_string("progress.starting"))
        
        try:
            # Process filenames
            filenames = [line.strip() for line in input_text.splitlines() if line.strip()]
            
            # Create searcher instance
            searcher = EverythingSearcher(
                input_text='\n'.join(filenames),
                copy_path=self.copy_path.get() if self.copy_path.get() else None,
                move_path=self.move_path.get() if self.move_path.get() else None,
                log_path="logs" if self.log_enabled.get() else None,
                match_folder_structure=self.match_folder_structure.get(),
                delete_mode=self.delete_mode.get(),
                log_callback=lambda msg: self.log_output.insert(tk.END, msg + "\n"),
                progress_callback=self.update_progress,
                regex_filter=regex_pattern if regex_pattern else None,
                lang=self.lang  # Pass the language manager
            )
            
            # Clear output
            self.log_output.delete('1.0', tk.END)
            
            # Process files
            searcher.process_files()
            self.log_output.insert(tk.END, "\n" + self.lang.get_string("progress.completed"))
            
        except Exception as e:
            messagebox.showerror("Error", self.lang.get_string("errors.process_error").format(str(e)))
            self.log_output.insert(tk.END, f"\n{self.lang.get_string('errors.process_error').format(str(e))}")
        finally:
            # Re-enable process button
            self.process_button.state(['!disabled'])
            self.progress_label.config(text=self.lang.get_string("progress.ready"))

    def browse_output(self, output_type):
        """Browse for output directory"""
        folder = filedialog.askdirectory()
        if folder:
            if output_type == "copy":
                self.copy_path.set(folder)
            else:
                self.move_path.set(folder)

    def clear_form(self):
        """Clear all form inputs"""
        self.input_text.delete('1.0', tk.END)
        self.input_text.insert('1.0', self.lang.get_string("input.default_text"))
        self.copy_path.set('')
        self.move_path.set('')
        self.log_enabled.set(False)
        self.match_folder_structure.set(True)
        self.delete_mode.set(False)
        self.regex_filter.set('')
        self.log_output.delete('1.0', tk.END)
        self.progress_var.set(0)
        self.progress_label.config(text="Ready")

    def on_input_focus_in(self, event):
        """Handle input focus in event"""
        current_text = self.input_text.get('1.0', 'end-1c').strip()
        if current_text == self.input_text.default_text:
            self.input_text.delete('1.0', tk.END)
            self.input_text.configure(fg=self.input_text.normal_color)

    def on_input_focus_out(self, event):
        """Handle input focus out event"""
        current_text = self.input_text.get('1.0', 'end-1c').strip()
        if not current_text:
            self.input_text.delete('1.0', tk.END)
            self.input_text.configure(fg=self.input_text.default_color)
            self.input_text.insert('1.0', self.input_text.default_text)
        else:
            self.input_text.configure(fg=self.input_text.normal_color)

    def _add_tooltip(self, widget, key):
        """Add a tooltip to a widget"""
        # Store the key for later updates
        widget.tooltip_key = key
        
        tooltip_text = self.lang.get_tooltip(key)
        if tooltip_text:
            widget.tooltip = tooltip_text  # Store current tooltip text
            
            def show_tooltip(event):
                if hasattr(widget, 'tooltip_window'):
                    widget.tooltip_window.destroy()
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                
                # Use current tooltip text from widget
                label = ttk.Label(tooltip, text=widget.tooltip, justify='left',
                                relief='solid', borderwidth=1)
                label.pack()
                
                widget.tooltip_window = tooltip
            
            def hide_tooltip(event):
                if hasattr(widget, 'tooltip_window'):
                    widget.tooltip_window.destroy()
                    delattr(widget, 'tooltip_window')
            
            widget.bind('<Enter>', show_tooltip)
            widget.bind('<Leave>', hide_tooltip)

    def _get_language_name(self, lang_code):
        """Get the display name for a language code"""
        self.lang.set_language(lang_code)
        name = self.lang.get_string("language.name")
        self.lang.set_language(self._initial_language)
        return name

    def _on_language_change(self, event=None):
        """Handle language change event"""
        # Get the selected language
        selected_language = self.current_language.get()
        
        # Update language manager
        if self.lang.set_language(selected_language):
            # Update all GUI strings
            self._update_gui_strings()
            
            # Save the selected language in config
            self.config.set("Interface", "language", selected_language)
            self.config.save_config()

    def _get_all_widgets(self, widget):
        """Recursively get all child widgets"""
        widgets = [widget]
        for child in widget.winfo_children():
            widgets.extend(self._get_all_widgets(child))
        return widgets

    def _update_gui_strings(self):
        """Update all GUI strings after language change"""
        # Update window title
        self.root.title(self.lang.get_string("window.title"))
        
        # Update menu bar
        if hasattr(self, 'menubar'):
            # Update language menu label
            for i in range(self.menubar.index("end") + 1):
                if self.menubar.type(i) == "cascade":
                    menu_widget = self.menubar.nametowidget(self.menubar.entrycget(i, "menu"))
                    if menu_widget == self.language_menu:
                        new_label = self.lang.get_string("menu.language")
                        self.menubar.entryconfigure(i, label=new_label)
                        break
        
        def update_widget_text(widget):
            """Update text for a single widget based on its string key"""
            if hasattr(widget, 'string_key'):
                new_text = self.lang.get_string(widget.string_key)
                if isinstance(widget, (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.LabelFrame)):
                    widget.config(text=new_text)
                elif isinstance(widget, scrolledtext.ScrolledText):
                    current_text = widget.get('1.0', 'end-1c').strip()
                    # Only update if it's showing the default text
                    if not current_text or current_text == widget.default_text:
                        widget.delete('1.0', tk.END)
                        widget.default_text = new_text  # Update the stored default text
                        if not widget.focus_get() == widget:  # Only show placeholder if not focused
                            widget.configure(fg=widget.default_color)
                            widget.insert('1.0', new_text)
                        else:
                            widget.configure(fg=widget.normal_color)
        
        def update_container_widgets(container):
            """Recursively update all widgets in a container"""
            for widget in container.winfo_children():
                update_widget_text(widget)
                if widget.winfo_children():
                    update_container_widgets(widget)
        
        # Update all widgets starting from main frame
        update_container_widgets(self.main_frame)
        
        # Update tooltips
        self._update_tooltips()

    def _update_tooltips(self):
        """Update all tooltips after language change"""
        def update_container_tooltips(container):
            for widget in container.winfo_children():
                if hasattr(widget, 'tooltip_key'):
                    tooltip_text = self.lang.get_tooltip(widget.tooltip_key)
                    if tooltip_text:
                        widget.tooltip = tooltip_text
                
                # Recursively update tooltips in child containers
                if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                    update_container_tooltips(widget)
        
        # Update all tooltips starting from main frame
        update_container_tooltips(self.main_frame)

    def _confirm_action(self, action_type):
        """Show confirmation dialog for dangerous actions"""
        if action_type == "delete":
            return messagebox.askyesno(
                self.lang.get_string("confirmations.delete_title"),
                self.lang.get_string("confirmations.delete_message")
            )
        elif action_type == "move":
            return messagebox.askyesno(
                self.lang.get_string("confirmations.move_title"),
                self.lang.get_string("confirmations.move_message")
            )
        return True

    def _load_settings(self):
        """Load settings from config"""
        # Load language
        language = self.config.get("Interface", "language", "English")
        if language in self.lang.get_languages():
            self.current_language.set(language)
            self.lang.set_language(language)
        
        # Load search settings
        self.regex_filter.set(self.config.get("Search", "regex_filter", ""))
        
        # Load output settings
        self.log_enabled.set(self.config.get_bool("Output", "enable_logging", False))
        self.match_folder_structure.set(self.config.get_bool("Output", "match_folder_structure", True))
        
        # Load paths
        self.copy_path.set(self.config.get("Paths", "default_copy_folder", ""))
        self.move_path.set(self.config.get("Paths", "default_move_folder", ""))
        
        # Always set delete mode to False for safety
        self.delete_mode.set(False)

    def _on_closing(self):
        """Save settings before closing"""
        # Save language
        self.config.set("Interface", "language", self.current_language.get())
        
        # Save search settings
        self.config.set("Search", "regex_filter", self.regex_filter.get())
        
        # Save output settings
        self.config.set("Output", "enable_logging", str(self.log_enabled.get()))
        self.config.set("Output", "match_folder_structure", str(self.match_folder_structure.get()))
        
        # Save paths
        self.config.set("Paths", "default_copy_folder", self.copy_path.get())
        self.config.set("Paths", "default_move_folder", self.move_path.get())
        
        # Save config to file
        self.config.save_config()
        self.root.destroy()

def parse_args():
    parser = argparse.ArgumentParser(description="Batch process files using Everything search")
    parser.add_argument("--input", help="Input file containing filenames")
    parser.add_argument("--copy-to", help="Copy matching files to this folder")
    parser.add_argument("--move-to", help="Move matching files to this folder")
    parser.add_argument("--log-path", help="Path to store log files")
    parser.add_argument("--delete", action="store_true", help="Delete matching files")
    parser.add_argument("--no-structure", action="store_true", help="Don't maintain folder structure")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # If command line arguments are provided, run in CLI mode
    if args.input:
        searcher = EverythingSearcher(
            input_file=args.input,
            copy_path=args.copy_to,
            move_path=args.move_to,
            log_path=args.log_path,
            match_folder_structure=not args.no_structure,
            delete_mode=args.delete
        )
        searcher.process_files()
    # Otherwise, launch GUI
    else:
        gui = SearchGUI()
        gui.root.mainloop()

if __name__ == "__main__":
    main() 