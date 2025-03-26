# Everything Batch Search

A powerful batch file processing tool that uses Everything search engine to quickly locate and process files. Search for multiple filenames at once and perform bulk operations with them.

Use it to find duplicates, or manage multiple files at the same time even if you made copies of them and you forgot where they all are now...

![image](https://github.com/user-attachments/assets/5b3c67b8-d6b3-42b5-bfc7-a6bba56eefba)

## Requirements

- Windows OS
- [Everything search engine](https://www.voidtools.com/downloads/) installed with CLI option
- Python 3.6 or higher

## Installation

1. Clone or download this repository
2. Run `venv_create.bat` to create a virtual environment:
   - Choose your Python version when prompted
   - Accept the default virtual environment name (venv) or choose your own
   - Allow pip upgrade when prompted
   - Allow installation of dependencies from requirements.txt

The script will create:
- A virtual environment
- `venv_activate.bat` for activating the environment
- `venv_update.bat` for updating pip

Alternatively, create a virtual environment yourself.

## Usage

### GUI Mode (Default)
Run the included `LaunchEverythingBatch.bat` or `python everything_batch.py` to launch the graphical interface.

#### Input Options
- **Input Files**: Enter filenames to search for, one per line
- **Regex Filter**: Apply regular expression patterns to filter results further
- **Match Folder Structure**: Preserve original folder structure in output

#### Output Options
- **Copy To**: Copy matching files to specified folder
- **Move To**: Move matching files to specified folder (use with extreme caution)
- **Enable Logging**: Save search results to log files
> [!WARNING]
> - **Delete Matching Files**: Remove found files (use with extreme caution)

### Command Line Interface

Run `python everything_batch.py --help` for all available options.

Basic usage:
```bash
python everything_batch.py --input "path/to/file/list.txt"
```

Options:
- `--input`: File containing list of filenames to search
- `--copy-to`: Copy matching files
- `--move-to`: Move matching files
- `--log-path`: Path for log files
- `--delete`: Delete matching files
- `--no-structure`: Don't maintain folder structure

## Features

- Fast multi-file search using Everything search engine
- Multilingual interface (19 languages included)
- Batch processing of search results
- Regular expression filtering
- Option to preserve folder structure in output
- Safe operation with confirmation for risky actions
- Comprehensive logging system
- File copying, moving, and deletion capabilities
- Both GUI and CLI interfaces
- Protects key folders on a Windows operating system

## Notes

- Everything search engine must be installed with the CLI option
- Everything service must be running for this tool to work
- Wait for Everything to finish indexing files before using this tool
- Moving and deleting files are permanent - use with caution
- Regular expressions can be used to further refine search results
- Logs are saved with timestamps in the logs folder

## Languages Supported

The interface is available in multiple languages including:
- English
- Spanish
- French
- German
- Italian
- Chinese
- Japanese
- Korean
- Arabic
- Greek
- and more...

## License

See the LICENSE file for details. 
