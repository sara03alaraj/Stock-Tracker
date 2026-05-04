# Deployment Guide

## Overview
This repository contains a Streamlit-based alert system application (`scraper_app.py`). It is ready to deploy on an Ubuntu Linux server after installing the required Python dependencies and ensuring file naming is Linux-safe.

## Requirements
- Python 3.10+ or Python 3.11
- use `requirements.txt` for installation

## Python packages
- streamlit
- requests
- beautifulsoup4
- pandas
- apscheduler
- pytz
- urllib3
- PyPDF2

## Optional files and cleanup
- Do not deploy `.venv/` or `.venv-1/` directories
- Do not deploy local state files such as `last_run.json` or `Stock_Update_Draft.eml`
- The app now detects the logo PNG dynamically from any file named case-insensitively as `logo.png`

## Setup steps on Ubuntu
1. Connect to the Ubuntu server.
2. Install Python and pip if not already installed:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip
   ```
3. Clone or copy the repository to the server.
4. Create a virtual environment in the project directory:
   ```bash
   python3 -m venv .venv
   ```
5. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
6. Install the required packages from `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
7. Run the Streamlit app:
   ```bash
   streamlit run scraper_app.py
   ```

## Running in the background
For production or long-running usage, consider using a process manager such as `systemd`, `tmux`, or `screen`.

### Example using `screen`
```bash
screen -S alert-system
source .venv/bin/activate
streamlit run scraper_app.py
```

## Notes
- If you use `systemd`, configure the service to activate the virtual environment and run the Streamlit command.
- If `Logo.png` is present, verify the filename casing matches `LOGO_FILE` in `scraper_app.py`.
