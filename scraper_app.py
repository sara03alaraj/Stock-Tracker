import streamlit as st
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import pandas as pd
from datetime import datetime
import time
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
import base64  
import urllib3
import re

# Suppress insecure request warnings for regional sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# --- PAGE SETUP ---
st.set_page_config(page_title="Stock Market Updates", page_icon="📈", layout="centered")

from theme import load_theme

def inject_custom_css():
    st.markdown("""
        <style>
        div[data-testid="stAlert"] { width: fit-content !important; }
        div[data-testid="stDownloadButton"] button, 
        div[data-testid="stDownloadButton"] button p { color: #FFFFFF !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

# --- CONFIGURATION ---
CREDENTIALS = {"admin": "AAC@2010"} 
STATE_FILE = "last_run.json"

BASE_DIR = Path(__file__).resolve().parent

def find_logo_file():
    for p in BASE_DIR.glob("*.png"):
        if p.name.lower() == "logo.png":
            return str(p)
    return str(BASE_DIR / "logo.png")

LOGO_FILE = find_logo_file()

MARKETS = {
    "Jordan (Amman Stock Exchange)": {
        "url": "https://www.ase.com.jo/en/disclosures",
        "companies": {
            "MEIN": "MIDDLE EAST INSURANCE", "AAIN": "AL-NISR AL-ARABI INSURANCE",
            "JOIN": "JORDAN INSURANCE", "AICJ": "ARABIA INSURANCE COMPANY - JORDAN",
            "DICL": "DELTA INSURANCE", "JERY": "JERUSALEM INSURANCE",
            "UNIN": "THE UNITED INSURANCE", "JOFR": "JORDAN FRENCH INSURANCE",
            "MIIC": "AL MANARA ISLAMIC INSURANCE COMPANY", "GIGJ": "GULF INSURANCE GROUP - JORDAN",
            "NAAI": "NATIONAL INSURANCE", "JIJC": "JORDAN INTERNATIONAL INSURANCE",
            "AMMI": "EURO ARAB INSURANCE GROUP", "TIIC": "THE ISLAMIC INSURANCE",
            "FINS": "FIRST INSURANCE", "ARAS": "ARAB ASSURERS", "ARGR":"ARAB JOR INSUR"
        }
    },
    "Palestine (PEX & PCMA)": {
        "url": "https://pex.ps", 
        "companies": {} 
    },
    "Iraq (Insurance Diwan)": {
        "url": "https://insurancediwan.gov.iq/",
        "companies": {}
    }
}

ARABIC_MONTHS = {
    "يناير": "01", "كانون الثاني": "01",
    "فبراير": "02", "شباط": "02",
    "مارس": "03", "آذار": "03",
    "أبريل": "04", "نيسان": "04",
    "مايو": "05", "أيار": "05",
    "يونيو": "06", "حزيران": "06",
    "يوليو": "07", "تموز": "07",
    "أغسطس": "08", "آب": "08",
    "سبتمبر": "09", "أيلول": "09",
    "أكتوبر": "10", "تشرين الأول": "10",
    "نوفمبر": "11", "تشرين الثاني": "11",
    "ديسمبر": "12", "كانون الأول": "12"
}

ENGLISH_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12"
}

# --- STATE MANAGEMENT ---
def get_app_state(market_name):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                market_data = data.get(market_name, {})
                last_run_str = market_data.get("last_run", "2000-01-01T00:00:00")
                last_run = datetime.fromisoformat(last_run_str)
                seen_disclosures = market_data.get("seen_disclosures", [])
                has_unread_alerts = market_data.get("has_unread_alerts", False)
                cached_data = market_data.get("cached_data", {})
                return last_run, seen_disclosures, has_unread_alerts, cached_data
        except Exception:
            pass
    return datetime.min, [], False, {}

def update_app_state(market_name, seen_disclosures, has_unread_alerts, cached_data=None):
    if cached_data is None: cached_data = {}
    now = datetime.now()
    cleaned_seen = []
    
    # NEW MEMORY ADJUSTMENT: Delete all old dates, keep only today's seen disclosures
    for uid in seen_disclosures:
        try:
            date_str = uid.split("_")[-1]
            try: uid_date = datetime.strptime(date_str, "%d/%m/%Y").date()
            except: uid_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Keep ONLY if it is exactly today's date
            if uid_date == now.date(): 
                cleaned_seen.append(uid)
        except Exception: 
            pass
            
    data = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: data = json.load(f)
        except: pass
            
    data[market_name] = {
        "last_run": now.isoformat(),
        "seen_disclosures": cleaned_seen,
        "has_unread_alerts": has_unread_alerts,
        "cached_data": cached_data
    }
    with open(STATE_FILE, "w") as f: json.dump(data, f, indent=4)

def clear_unread_alerts(market_name):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: data = json.load(f)
            if market_name in data:
                data[market_name]["has_unread_alerts"] = False
                data[market_name]["cached_data"] = {}
            with open(STATE_FILE, "w") as f: json.dump(data, f, indent=4)
        except: pass

def cleanup_old_files():
    for filename in os.listdir():
        if filename.endswith(('.pdf', '.xbrl', '.xlsx', '.zip', '.eml')):
            try: os.remove(filename)
            except: pass

def create_email_draft_file(subject, body, file_paths, draft_filename="Stock_Update_Draft.eml"):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['To'] = "" 
    msg['X-Unsent'] = '1' 
    msg.set_content(body)
    html_content = body.replace('\n', '<br>')
    
    # Adding basic styling to make the links look clickable in Outlook
    html_body = f"<html><head><style>body, div, p, span {{ font-family: 'Calibri', sans-serif; font-size: 11pt; color: #000000; }} a {{ color: #004475; text-decoration: underline; }}</style></head><body><div>{html_content}</div></body></html>"
    msg.add_alternative(html_body, subtype='html')

    if file_paths:
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=os.path.basename(file_path))
            except Exception as e: st.error(f"Failed to attach {file_path}. Error: {e}")

    with open(draft_filename, 'wb') as f: f.write(bytes(msg))
    return draft_filename

# --- SCRAPING LOGIC ---
def scrape_iraq_disclosures():
    iraq_urls = {
        "قوانين ديوان التأمين": "https://insurancediwan.gov.iq/?page_id=64262&lang=ar",
        "أنظمة ديوان التأمين": "https://insurancediwan.gov.iq/?page_id=65912&lang=ar",
        "تعليمات ديوان التأمين": "https://insurancediwan.gov.iq/?page_id=64230&lang=ar",
        "البحوث و الدراسات": "https://insurancediwan.gov.iq/?page_id=65738&lang=ar",
        "تعاميم ديوان التأمين": "https://insurancediwan.gov.iq/?page_id=67060&lang=ar",
        "نماذج و وثائق": "https://insurancediwan.gov.iq/?page_id=68444&lang=ar",
        "اخر الاخبار": "https://insurancediwan.gov.iq/?page_id=64614&lang=ar"
    }
    data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    status_box = st.empty()
    status_box.info("🚀 Scanning Iraqi Insurance Diwan (Extracting True Dates)...")
    
    for category, url in iraq_urls.items():
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 1. Scrape News Links with Exact Dates
                if category == "اخر الاخبار":
                    post_items = soup.find_all('div', class_='elespare-posts-grid-post-items')
                    for item in post_items:
                        title_tag = item.find(['h2', 'h3', 'h4'])
                        a_tag = title_tag.find('a', href=True) if title_tag else item.find('a', href=True)
                        
                        if a_tag:
                            href = a_tag['href']
                            title = a_tag.text.strip()
                            
                            item_text = item.get_text(separator=" ")
                            clean_text = item_text.replace('،', ' ').replace(',', ' ').replace('-', ' ').replace('\n', ' ')
                            clean_text = re.sub(r'\s+', ' ', clean_text).lower() 
                            
                            date_str = None
                            for en_m, num_m in ENGLISH_MONTHS.items():
                                if en_m in clean_text:
                                    pattern = en_m + r'\s+(\d{1,2})\s+(\d{4})'
                                    match = re.search(pattern, clean_text)
                                    if match:
                                        day = match.group(1).zfill(2)
                                        year = match.group(2)
                                        date_str = f"{day}/{num_m}/{year}"
                                        break
                                        
                            if not date_str:
                                for ar_m, num_m in ARABIC_MONTHS.items():
                                    if ar_m in clean_text:
                                        pattern = r'(\d{1,2})\s+' + ar_m + r'\s+(\d{4})'
                                        match = re.search(pattern, clean_text)
                                        if match:
                                            day = match.group(1).zfill(2)
                                            year = match.group(2)
                                            date_str = f"{day}/{num_m}/{year}"
                                            break
                                        
                            if not date_str:
                                wp_match = re.search(r'/uploads/(\d{4})/(\d{2})/', href)
                                if wp_match: date_str = f"01/{wp_match.group(2)}/{wp_match.group(1)}"
                                    
                            if not date_str:
                                date_str = datetime.now().strftime("%d/%m/%Y")
                            
                            if len(title) > 5 and not any(d['Disclosure'] == title for d in data):
                                data.append({
                                    "Disclosure": title, "Symbol": "DIWAN-NEWS",
                                    "Security Name": "ديوان التأمين العراقي", "Category": category,
                                    "Date": date_str, "File_Links": {'pdf': href} 
                                })

                # 2. Scrape Documents and PDFs
                else:
                    links = soup.find_all('a', href=True)
                    for a in links:
                        href = a['href']
                        if href.endswith('.pdf') or href.endswith('.docx') or href.endswith('.doc') or 'download' in href.lower():
                            if 'wp-content/plugins' in href or 'wp-content/themes' in href: continue 
                            
                            title = a.text.strip()
                            if len(title) < 5 or title.lower() in ['تحميل', 'download', 'pdf']:
                                parent = a.parent
                                title = parent.text.replace(a.text, '').strip()
                                if len(title) < 5 and parent.parent: title = parent.parent.text.replace(a.text, '').strip()
                            
                            title = title.replace('\n', ' ').strip()
                            if not title: title = f"وثيقة - {category}"
                            
                            date_str = None
                            wp_match = re.search(r'/uploads/(\d{4})/(\d{2})/', href)
                            if wp_match: date_str = f"01/{wp_match.group(2)}/{wp_match.group(1)}"
                            
                            if not date_str:
                                try:
                                    head_resp = requests.head(href, verify=False, timeout=3)
                                    last_mod = head_resp.headers.get('Last-Modified')
                                    if last_mod:
                                        parsed_dt = parsedate_to_datetime(last_mod)
                                        date_str = parsed_dt.strftime("%d/%m/%Y")
                                except: pass
                                
                            if not date_str: date_str = datetime.now().strftime("%d/%m/%Y")
                            
                            if not any(d['File_Links'].get('pdf') == href for d in data):
                                data.append({
                                    "Disclosure": title[:150], "Symbol": "DIWAN",
                                    "Security Name": "ديوان التأمين العراقي", "Category": category,
                                    "Date": date_str, "File_Links": {'pdf': href}
                                })
                                
        except Exception as e: print(f"Error scraping Iraq category {category}: {e}")
            
    status_box.empty()
    return data

def scrape_jordan_disclosures(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table: return []
    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:] 
    
    data = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 6: continue
        disclosure_name = cols[0].text.strip()
        symbol = cols[1].text.strip()
        security_name = cols[2].text.strip()
        category = cols[3].text.strip()
        date_str = cols[4].text.strip() 
        file_links = {}
        for i, key in enumerate(['pdf', 'xbrl', 'xlsx', 'zip'], start=5):
            if len(cols) > i:
                tag = cols[i].find('a')
                if tag and 'href' in tag.attrs:
                    link = tag['href']
                    if not link.startswith('http'): link = "https://www.ase.com.jo" + link
                    file_links[key] = link
        data.append({
            "Disclosure": disclosure_name, "Symbol": symbol, "Security Name": security_name,
            "Category": category, "Date": date_str, "File_Links": file_links
        })
    return data

def scrape_pcma_disclosures():
    url = "https://www.pcma.ps/%d8%a7%d9%81%d8%b5%d8%a7%d8%ad%d8%a7%d8%aa/"
    data = []
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table')
        
        for table in tables:
            date_col_index = -1
            headers = table.find_all('th')
            for idx, th in enumerate(headers):
                if "تاريخ" in th.text:
                    date_col_index = idx
                    break
                    
            if date_col_index == -1: date_col_index = 2 
                
            for row in table.find_all('tr'):
                if "تأمين" in row.text: 
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 3:
                        company_name = "PCMA Insurance Company"
                        for col in cols:
                            if "تأمين" in col.text:
                                company_name = col.text.strip()
                                break
                                
                        extracted_date_str = ""
                        try:
                            if len(cols) > date_col_index:
                                raw_date = cols[date_col_index].text.strip()
                                date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', raw_date)
                                if date_match: extracted_date_str = date_match.group(0)
                        except: pass
                        
                        if not extracted_date_str: extracted_date_str = datetime.now().strftime("%d/%m/%Y")
                            
                        try:
                            if "-" in extracted_date_str: dt = datetime.strptime(extracted_date_str, "%Y-%m-%d")
                            else: dt = datetime.strptime(extracted_date_str, "%d/%m/%Y")
                            extracted_date_str = dt.strftime("%d/%m/%Y")
                        except: pass
                        
                        a_tag = row.find('a', href=True)
                        if a_tag:
                            link = a_tag['href']
                            if not link.startswith('http'): link = "https://www.pcma.ps" + link
                            disclosure_name = a_tag.text.strip() or "General Disclosure"
                            data.append({
                                "Disclosure": disclosure_name, "Symbol": "PCMA",
                                "Security Name": company_name, "Category": "PCMA Market Disclosure",
                                "Date": extracted_date_str, "File_Links": {"pdf": link}
                            })
    except Exception as e: print("PCMA Scrape Error:", e)
    return data

def scrape_pex_disclosures_via_api():
    data = []
    url_list = "https://webapi.pex.ps/api/GetAllDisclosures"
    url_details = "https://webapi.pex.ps/api/GetDisclosureDetails"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/json"
    }
    
    known_insurances = {
        "MIC": "Al Mashreq Insurance", "NIC": "National Insurance",
        "TRUST": "Trust International Insurance", "PICO": "Palestine Insurance",
        "GUI": "Global United Insurance", "AIG": "Ahliya Insurance",
        "TIC": "Al-Takaful Palestinian Insurance", "TPIC": "Tamkeen Palestinian Insurance"
    }
    
    status_box = st.empty()
    status_box.info("🚀 Contacting PEX Secure Database directly...")
    
    for symbol, name in known_insurances.items():
        try:
            payload = {
                "DateRangeModel": {
                    "StartDate": "2025-01-01", 
                    "EndDate": datetime.now().strftime("%Y-%m-%d")
                },
                "CompanySymbol": symbol,
                "PageIndex": 1,
                "PageSize": 50 
            }
            
            response = requests.post(url_list, json=payload, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                json_data = response.json()
                items = json_data.get("items", [])
                valid_files = 0
                
                for item in items:
                    raw_date = item.get("DisclosureDate", "")
                    date_str = raw_date.split("T")[0] if "T" in raw_date else raw_date
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                        date_str = parsed_date.strftime("%d/%m/%Y")
                    except: pass
                    
                    title_obj = item.get("MainTitle", {})
                    disclosure_name = title_obj.get("Ar", "") or title_obj.get("En", "PEX Disclosure")
                    disclosure_name = disclosure_name.replace('\r', '').replace('\n', ' ')
                    disclosure_name = disclosure_name[:80] + "..." if len(disclosure_name) > 80 else disclosure_name
                    
                    disclosure_id = item.get("DisclosureId")
                    physical_pdf_path = None
                    
                    if disclosure_id:
                        details_payload = {"Id": disclosure_id}
                        try:
                            details_resp = requests.post(url_details, json=details_payload, headers=headers, verify=False, timeout=5)
                            if details_resp.status_code == 200:
                                details_data = details_resp.json()
                                for key, val in details_data.items():
                                    if isinstance(val, str) and (val.endswith('.pdf') or 'http' in val or 'files' in val.lower()):
                                        physical_pdf_path = val
                                        break
                                        
                                if physical_pdf_path:
                                    if not physical_pdf_path.startswith('http'):
                                        physical_pdf_path = "https://webapi.pex.ps" + physical_pdf_path if physical_pdf_path.startswith('/') else "https://webapi.pex.ps/" + physical_pdf_path
                                        
                                    pdf_data = requests.get(physical_pdf_path, verify=False, timeout=10)
                                    if pdf_data.status_code == 200:
                                        safe_name = disclosure_name.replace("/", "-").replace("\\", "-").replace(":", "")[:60]
                                        local_filename = f"{safe_name}_{symbol}.pdf"
                                        with open(local_filename, "wb") as f: f.write(pdf_data.content)
                                        physical_pdf_path = f"local_file:{local_filename}"
                        except: pass
                    
                    ui_link = f"https://www.pex.ps/company-profile/{symbol}?tab=disclosures"
                    
                    if not any(d['Disclosure'] == disclosure_name and d['Date'] == date_str for d in data):
                        data.append({
                            "Disclosure": disclosure_name,
                            "Symbol": symbol, "Security Name": name,
                            "Category": "PEX Market Disclosure",
                            "Date": date_str, 
                            "File_Links": {'pdf': ui_link, 'physical_file': physical_pdf_path}
                        })
                        valid_files += 1
                        
                if valid_files > 0: status_box.success(f"✅ [PEX] Extracted {valid_files} items and PDFs for {symbol}!")
                
        except Exception as e: status_box.error(f"❌ [PEX] Error querying {symbol}: {e}")
            
    time.sleep(2)
    status_box.empty()
    return data

def process_updates(market_name, is_background_job=False):
    last_run, seen_disclosures, current_unread_status, current_cached_data = get_app_state(market_name)
    last_run_date = last_run.date() 
    updates_found = 0
    all_downloaded_files = []
    extracted_table_data = [] 
    email_body = f"Dear Mr .Ala,\n\nPlease find below the latest Stock Exchange updates for {market_name}:\n\n"
    
    if market_name == "Jordan (Amman Stock Exchange)":
        market_data = MARKETS[market_name]
        for symbol in market_data["companies"].keys():
            search_url = f"{market_data['url']}?symbol={symbol}"
            scraped_data = scrape_jordan_disclosures(search_url)
            if not scraped_data: continue

            for item in scraped_data:
                item_symbol = item["Symbol"]
                date_str = item["Date"]
                file_links = item["File_Links"]
                disclosure_name = item["Disclosure"]
                
                try: disclosure_date = datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError: continue 
                
                unique_id = f"{item_symbol}_{disclosure_name}_{date_str}"
                
                if disclosure_date.date() >= last_run_date and unique_id not in seen_disclosures:
                    full_company_name = market_data["companies"][item_symbol] 
                    row_files = [] 
                    if file_links:
                        for ext, link in file_links.items():
                            try:
                                file_resp = requests.get(link, verify=False)
                                safe_name = disclosure_name.replace("/", "-").replace("\\", "-").replace(":", "")
                                file_name = f"{safe_name}_{item_symbol}.{ext}" 
                                with open(file_name, "wb") as f: f.write(file_resp.content)
                                all_downloaded_files.append(file_name)
                                row_files.append(file_name) 
                            except: pass
                    
                    extracted_table_data.append({
                        "Attach": True, "Disclosure": disclosure_name, "Symbol": item_symbol,
                        "Security's name": full_company_name, "Category": item["Category"],
                        "Date": date_str, "PDF": file_links.get('pdf', None), "XBRL": file_links.get('xbrl', None),
                        "EXCEL": file_links.get('xlsx', None), "ZIP": file_links.get('zip', None), "Hidden_Files": row_files 
                    })
                    email_body += f"• {full_company_name} - {item['Category']} [{date_str}]\n"
                    seen_disclosures.append(unique_id)
                    updates_found += 1

    elif market_name == "Palestine (PEX & PCMA)":
        pcma_data = scrape_pcma_disclosures()
        pex_data = scrape_pex_disclosures_via_api() 
        scraped_data = pcma_data + pex_data
            
        for item in scraped_data:
            item_symbol = item["Symbol"]
            date_str = item["Date"]
            file_links = item["File_Links"]
            disclosure_name = item["Disclosure"]
            
            try: disclosure_date = datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                try: disclosure_date = datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    try: disclosure_date = datetime.strptime(date_str, "%Y/%m/%d")
                    except: disclosure_date = datetime.now() 
            
            unique_id = f"{item_symbol}_{disclosure_name}_{date_str}"
            
            if disclosure_date.date() >= last_run_date and unique_id not in seen_disclosures:
                row_files = [] 
                
                if item_symbol == "PCMA" and file_links:
                    for ext, link in file_links.items():
                        try:
                            file_resp = requests.get(link, verify=False)
                            safe_name = disclosure_name.replace("/", "-").replace("\\", "-").replace(":", "")[:100]
                            file_name = f"{safe_name}_{item_symbol}.{ext}" 
                            with open(file_name, "wb") as f: f.write(file_resp.content)
                            all_downloaded_files.append(file_name)
                            row_files.append(file_name) 
                        except: pass
                
                if item_symbol != "PCMA":
                    physical_file = file_links.get('physical_file')
                    if physical_file and physical_file.startswith('local_file:'):
                        actual_filename = physical_file.replace('local_file:', '')
                        all_downloaded_files.append(actual_filename)
                        row_files.append(actual_filename)
                
                extracted_table_data.append({
                    "Attach": True, "Disclosure": disclosure_name, "Symbol": item_symbol,
                    "Security's name": item["Security Name"], "Category": item["Category"],
                    "Date": date_str, "PDF": file_links.get('pdf', None), "XBRL": file_links.get('xbrl', None),
                    "EXCEL": file_links.get('xlsx', None), "ZIP": file_links.get('zip', None), "Hidden_Files": row_files 
                })
                email_body += f"• {item['Security Name']} - {item['Category']} [{date_str}]\n"
                
                # Attach Link as PDF fallback if no physical file exists
                if not row_files and file_links.get('pdf'):
                    email_body += f"  ➔ Document Link: {file_links.get('pdf')}\n"
                    
                seen_disclosures.append(unique_id)
                updates_found += 1
                
    elif market_name == "Iraq (Insurance Diwan)":
        scraped_data = scrape_iraq_disclosures()
        
        for item in scraped_data:
            item_symbol = item["Symbol"]
            date_str = item["Date"]
            file_links = item["File_Links"]
            disclosure_name = item["Disclosure"]
            category = item["Category"]
            
            try: disclosure_date = datetime.strptime(date_str, "%d/%m/%Y")
            except: disclosure_date = datetime.now() 
            
            pdf_link_str = file_links.get('pdf', '')
            # Unique ID with date appended perfectly for memory parsing
            unique_id = f"IRAQ_{disclosure_name}_{pdf_link_str}_{date_str}"
            
            if disclosure_date.date() >= last_run_date and unique_id not in seen_disclosures:
                row_files = [] 
                
                if file_links and (pdf_link_str.endswith('.pdf') or pdf_link_str.endswith('.docx')):
                    try:
                        file_resp = requests.get(pdf_link_str, verify=False, timeout=15)
                        if file_resp.status_code == 200:
                            safe_name = disclosure_name.replace("/", "-").replace("\\", "-").replace(":", "")[:80]
                            file_name = f"{safe_name}_IRAQ.pdf" 
                            with open(file_name, "wb") as f: f.write(file_resp.content)
                            all_downloaded_files.append(file_name)
                            row_files.append(file_name) 
                    except: pass
                
                extracted_table_data.append({
                    "Attach": True, "Disclosure": disclosure_name, "Symbol": item_symbol,
                    "Security's name": item["Security Name"], "Category": category,
                    "Date": date_str, "PDF": pdf_link_str, "XBRL": None,
                    "EXCEL": None, "ZIP": None, "Hidden_Files": row_files 
                })
                email_body += f"• {item['Security Name']} - {category} - {disclosure_name[:60]}...\n"
                
                # Attach Link as PDF fallback if no physical file exists (e.g. News Link)
                if not row_files and pdf_link_str:
                    email_body += f"  ➔ News/Document Link: {pdf_link_str}\n"
                    
                seen_disclosures.append(unique_id)
                updates_found += 1
                
    if updates_found == 0:
        email_body = f"Dear Mr. Ala,\n\nPlease be advised that no new updates or files were found for {market_name}."
    else:
        email_body += "\n\nPlease find the relevant files attached or linked for your review.\n\nBest regards,\n\nAutomated Tracker"
        
    if is_background_job:
        new_unread = current_unread_status or (updates_found > 0)
        new_cache = {"email_body": email_body, "downloaded_files": all_downloaded_files, "update_count": updates_found, "table_data": extracted_table_data} if updates_found > 0 else current_cached_data
        update_app_state(market_name, seen_disclosures, new_unread, new_cache)
    else:
        update_app_state(market_name, seen_disclosures, False, {})
        
    return email_body, all_downloaded_files, updates_found, extracted_table_data

def scheduled_job():
    cleanup_old_files()
    for market in MARKETS.keys(): process_updates(market, is_background_job=True)

@st.cache_resource
def start_background_scheduler():
    scheduler = BackgroundScheduler(timezone=timezone('Asia/Amman'))
    scheduler.add_job(scheduled_job, 'cron', hour=13, minute=0) 
    #scheduler.start()
    return scheduler

global_scheduler = start_background_scheduler()

def login():
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=250)
        st.title("Stock Tracker")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if CREDENTIALS.get(username) == password:
                st.session_state["logged_in"] = True
                st.query_params["auth"] = "true" 
                st.rerun()
            else: st.error("Invalid Username or Password")

@st.dialog("✅ Background Updates Auto-Loaded!")
def auto_load_popup(count):
    st.success(f"The server extracted {count} updates while you were away!")
    if st.button("Awesome, thanks!"): st.rerun()

def main_app():
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "rb") as image_file: encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""<style>.floating-logo {{ position: fixed; top: 80px; left: 30px; width: 250px; z-index: 999999; }}</style><img src="data:image/png;base64,{encoded_string}" class="floating-logo">""", unsafe_allow_html=True)

    st.markdown("""<style>.logout-widget { position: fixed; top: 80px; right: 30px; z-index: 999999; text-align: center; } .logout-btn { background-color: #004475; color: #FFFFFF !important; border: 1px solid #004475; padding: 0.4rem 1.2rem; border-radius: 0.5rem; text-decoration: none !important; display: inline-block; font-weight: 600; } .logout-btn:hover { color: #FFFFFF !important; background-color: #003355; }</style><div class="logout-widget"><a href="?logout=true" target="_parent" class="logout-btn">Logout</a><div style="color:gray; font-size:0.85em; margin-top:5px;">👤 Admin</div></div>""", unsafe_allow_html=True)

    st.title("📈 Stock Market Updates")
    st.write("Multi-Market Disclosures Tracker")
    
    if "report_ready" not in st.session_state:
        st.session_state.update({"report_ready": False, "email_body": "", "downloaded_files": [], "update_count": 0, "table_data": []})

    st.markdown("---")
    st.subheader("Manual Data Extraction")
    
    col_input, _ = st.columns([4.5, 5.5])
    with col_input: selected_market = st.selectbox("Select Target Market:", list(MARKETS.keys()))
    
    last_run, _, has_unread_alerts, cached_data = get_app_state(selected_market)
    
    if has_unread_alerts and cached_data and cached_data.get("update_count", 0) > 0:
        st.session_state.update({"email_body": cached_data["email_body"], "downloaded_files": cached_data["downloaded_files"], "update_count": cached_data["update_count"], "table_data": cached_data["table_data"], "report_ready": True})
        clear_unread_alerts(selected_market)
        auto_load_popup(cached_data["update_count"])

    last_sync_placeholder = st.empty()
    last_sync_placeholder.info(f"**Last Sync ({selected_market}):** {last_run.strftime('%Y-%m-%d %H:%M:%S') if last_run != datetime.min else 'Never'}")
        
    col_btn_run, _ = st.columns([4, 6])
    with col_btn_run: run_pressed = st.button("Run Data Extraction", type="primary", use_container_width=True)
            
    if run_pressed:
        with st.spinner(f"Extracting updates from {selected_market}..."):
            cleanup_old_files() 
            result = process_updates(selected_market, is_background_job=False)
            if result[0] is None:
                st.warning("Could not find or parse the tables on the website.")
            else:
                st.session_state.update({"email_body": result[0], "downloaded_files": result[1], "report_ready": True, "update_count": result[2], "table_data": result[3]})
                st.success(f"Extraction complete. {result[2]} updates found.")
                new_last_run, _, _, _ = get_app_state(selected_market)
                last_sync_placeholder.info(f"**Last Sync ({selected_market}):** {new_last_run.strftime('%Y-%m-%d %H:%M:%S')}")

    if st.session_state["report_ready"] and st.session_state["update_count"] > 0:
        st.markdown("---")
        st.subheader("1. Review & Select Updates")
        
        df = pd.DataFrame(st.session_state["table_data"])
        if "Attach" not in df.columns: df.insert(0, "Attach", True)
        if "Hidden_Files" not in df.columns: df["Hidden_Files"] = [[] for _ in range(len(df))]

        if "editor_key" not in st.session_state: st.session_state["editor_key"] = 0
            
        edited_df = st.data_editor(
            df[['Attach', 'Disclosure', 'Symbol', "Security's name", 'Category', 'Date', 'PDF', 'XBRL', 'EXCEL', 'ZIP', 'Hidden_Files']],
            key=f"editor_{st.session_state['editor_key']}", use_container_width=True, hide_index=True,
            column_config={
                "Attach": st.column_config.CheckboxColumn("Attach?", default=True), "Hidden_Files": None, 
                "PDF": st.column_config.LinkColumn("Link / PDF", display_text="📄"), "XBRL": st.column_config.LinkColumn("XBRL", display_text="⚙️"),
                "EXCEL": st.column_config.LinkColumn("EXCEL", display_text="📊"), "ZIP": st.column_config.LinkColumn("ZIP", display_text="🗃️")
            },
            disabled=["Disclosure", "Symbol", "Security's name", "Category", "Date", "PDF", "XBRL", "EXCEL", "ZIP"]
        )
        
        st.session_state["table_data"] = edited_df.to_dict('records')
        all_attached = all(row.get("Attach", True) for row in st.session_state["table_data"])
        
        btn_placeholder = st.empty()
        with btn_placeholder.container():
            with st.columns([3, 7])[0]:
                if st.button("☑️ Select All Files" if all_attached else "☐ Select All Files", type="primary" if all_attached else "secondary", use_container_width=True):
                    for row in st.session_state["table_data"]: row["Attach"] = not all_attached 
                    st.session_state["editor_key"] += 1
                    st.rerun()
        
        selected_files, has_selections, dynamic_email_body = [], False, f"Dear Mr. Ala,\n\nPlease find below the latest Stock Exchange updates for {selected_market}:\n\n"
        
        for index, row in edited_df.iterrows():
            if row.get("Attach", False):
                has_selections = True
                sec_name = row.get("Security's name", "")
                cat = row.get("Category", "")
                date_val = row.get("Date", "")
                pdf_link = row.get("PDF", "")
                
                dynamic_email_body += f"• {sec_name} - {cat} [{date_val}]\n"
                
                # Dynamic Link attachment for Outlook drafts
                if isinstance(row.get("Hidden_Files"), list): 
                    selected_files.extend(row["Hidden_Files"])
                    if not row["Hidden_Files"] and pdf_link and isinstance(pdf_link, str) and pdf_link.startswith("http"):
                        dynamic_email_body += f"  ➔ Document Link: <a href='{pdf_link}'>{pdf_link}</a>\n"
                elif pdf_link and isinstance(pdf_link, str) and pdf_link.startswith("http"):
                    dynamic_email_body += f"  ➔ Document Link: <a href='{pdf_link}'>{pdf_link}</a>\n"
                    
        dynamic_email_body += "\n\nPlease find the relevant files attached or linked for your review.\n\nBest regards," if has_selections else "\n\nNo updates selected."
                
        st.markdown("---")
        st.subheader("2. Download Draft")
        
        draft_file = create_email_draft_file("Stock Exchange Updates", dynamic_email_body, selected_files)
        with open(draft_file, "rb") as f: eml_data = f.read()
            
        st.download_button(label=f"📥 Download Outlook Draft ({len(selected_files)} Files/Links)", data=eml_data, file_name="Stock_Update_Draft.eml", mime="message/rfc822", type="primary", on_click=cleanup_old_files)
        with st.expander("View Email Draft Text"): st.markdown(dynamic_email_body.replace('\n', '<br>'), unsafe_allow_html=True)

load_theme()
inject_custom_css()  

# --- Authentication & Routing ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "logout" in st.query_params:
    st.session_state.clear()
    st.session_state["logged_in"] = False
    st.query_params.clear()
    st.rerun()
    
elif "auth" in st.query_params:
    st.session_state["logged_in"] = True

# --- App Launch ---
if not st.session_state["logged_in"]:
    login()
else:
    main_app()