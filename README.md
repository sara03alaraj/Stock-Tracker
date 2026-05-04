# Stock Tracker Alert System

A Streamlit-based application for monitoring stock updates and sending alerts.

## Features

- Web scraping for stock information
- Automated scheduling with APScheduler
- PDF processing with PyPDF2
- Email alerts (configurable)
- Streamlit web interface

## Requirements

- Python 3.10 or higher
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/sara03alaraj/Stock-Tracker.git
   cd Stock-Tracker
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit application:
```bash
streamlit run scraper_app.py
```

The app will start a web server, typically accessible at `http://localhost:8501`.

## Deployment

For deployment instructions, see [deployment.md](deployment.md).

## Configuration

- Logo: Place a `logo.png` file in the root directory (case-insensitive detection)
- Email settings: Configure in the app interface
- Scheduling: Managed via APScheduler

## Notes

- Local state files like `last_run.json` are not included in version control
- Virtual environments should not be deployed