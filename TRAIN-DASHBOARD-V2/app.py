#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
from io import StringIO
import os, csv, requests
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from bs4 import BeautifulSoup
import re

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL et SUPABASE_KEY sont requis")

# Init Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Init FastAPI app
app = FastAPI(title="Train Dashboard V2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

DATASET_URL = "https://www.data.gouv.fr/fr/datasets/liste-des-trains-sncf-supprimes/"

def get_csv_urls_direct(year, month):
    r = requests.get(DATASET_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    mois_fr = {
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
        'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
    }
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Lien direct de téléchargement
        if re.match(r"^/fr/datasets/r/[a-f0-9\-]{36}$", href):
            # On cherche la date affichée à côté du lien
            parent = a.find_parent("div")
            if parent:
                text = parent.get_text()
                match = re.search(r"Mis à jour le (\d{1,2}) (\w+) (\d{4})", text)
                if match:
                    jour, mois_str, annee = match.groups()
                    if int(annee) == year and mois_fr.get(mois_str.lower(), 0) == month:
                        url = "https://www.data.gouv.fr" + href
                        urls.append(url)
    print(f"URLs trouvées pour {month}/{year} :", urls)
    return urls

def get_csv_urls_by_content(year, month):
    r = requests.get(DATASET_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/fr/datasets/r/[a-f0-9\-]{36}$", href):
            url = "https://www.data.gouv.fr" + href
            # On télécharge juste la première ligne du CSV pour vérifier la date
            try:
                resp = requests.get(url, stream=True)
                resp.raise_for_status()
                first_line = resp.iter_lines(decode_unicode=True)
                header = next(first_line)
                row = next(first_line)
                if row.startswith(f"{year}-{month:02d}"):
                    urls.append(url)
            except Exception as e:
                continue
    print(f"URLs trouvées par contenu pour {month}/{year} :", urls)
    return urls

# Service class
class TrainDataService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def get_trains_data(self, limit: int = 100, offset: int = 0, departure_date: Optional[str] = None):
        try:
            query = self.supabase.table('trains_supprimes').select('*')
            if departure_date:
                query = query.eq('departure_date', departure_date)
            query = query.range(offset, offset + limit - 1)
            result = query.execute()

            data = [{
                'departure_date': r.get('departure_date'),
                'departure': r.get('departure'),
                'arrival': r.get('arrival'),
                'departure_time': r.get('departure_time'),
                'arrival_time': r.get('arrival_time'),
                'headsign': r.get('headsign'),
                'type': r.get('type')
            } for r in result.data] if result.data else []

            return {"success": True, "data": data, "count": len(data), "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": [], "count": 0, "total": 0}

    def get_summary_stats(self):
        try:
            count_result = self.supabase.table('trains_supprimes').select('*', count='exact').execute()
            return {"success": True, "data": {"total_trains": count_result.count or 0}}
        except Exception as e:
            return {"success": False, "error": str(e), "data": {"total_trains": 0}}

    def insert_trains_from_csv_urls(self, urls: List[str]):
        inserted, skipped = 0, 0
        for url in urls:
            try:
                r = requests.get(url)
                r.raise_for_status()
                reader = csv.DictReader(StringIO(r.content.decode('utf-8')))
                for row in reader:
                    data = {
                        'type': row.get('type'),
                        'arrival': row.get('arrival'),
                        'headsign': row.get('headsign'),
                        'departure': row.get('departure'),
                        'arrival_time': row.get('arrival_time'),
                        'departure_date': row.get('departure_date'),
                        'departure_time': row.get('departure_time')
                    }
                    exists = self.supabase.table('trains_supprimes') \
                        .select('id') \
                        .eq('type', data['type']) \
                        .eq('arrival', data['arrival']) \
                        .eq('headsign', data['headsign']) \
                        .eq('departure', data['departure']) \
                        .eq('arrival_time', data['arrival_time']) \
                        .eq('departure_date', data['departure_date']) \
                        .eq('departure_time', data['departure_time']) \
                        .execute().data
                    if exists:
                        skipped += 1
                        continue
                    self.supabase.table('trains_supprimes').insert(data).execute()
                    inserted += 1
            except Exception:
                continue
        return {"inserted": inserted, "skipped": skipped}

    def import_for_month(self, year: int, month: int):
        urls = get_csv_urls_direct(year, month)
        return self.insert_trains_from_csv_urls(urls)

    def import_for_month_html(self, year: int, month: int):
        urls = get_csv_urls_direct(year, month)
        return self.insert_trains_from_csv_urls(urls)

    def import_for_month_direct(self, year: int, month: int):
        urls = get_csv_urls_direct(year, month)
        return self.insert_trains_from_csv_urls(urls)

    def import_for_month_by_content(self, year: int, month: int):
        urls = get_csv_urls_by_content(year, month)
        return self.insert_trains_from_csv_urls(urls)

# Service instance
train_service = TrainDataService(supabase)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    file_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="index.html non trouvé")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/trains")
async def get_trains(limit: int = 100, offset: int = 0, departure_date: Optional[str] = None):
    result = train_service.get_trains_data(limit, offset, departure_date)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get("/api/stats")
async def get_stats():
    result = train_service.get_summary_stats()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get("/api/health")
async def health_check():
    try:
        supabase.table('trains_supprimes').select('*', count='exact').limit(1).execute()
        return {"status": "healthy", "database": "connected", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e), "timestamp": datetime.now().isoformat()}

@app.post("/api/import")
async def import_trains(request: Request):
    body = await request.json()
    year = int(body.get('year', 0))
    month = int(body.get('month', 0))
    if not year or not month:
        raise HTTPException(status_code=400, detail="year et month requis (ex: 2025, 6)")
    return train_service.import_for_month_by_content(year, month)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
