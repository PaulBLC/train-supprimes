import os
import requests
import csv
from supabase import create_client
from dotenv import load_dotenv
import folium
import pandas as pd
from shiny import ui as shin_ui

# Charger les variables d'environnement
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Paramètres
API_URL = "https://www.data.gouv.fr/api/1/datasets/641b456a5374b1bdc9dce4cf/"
ANNEE = "2024"
MOIS_LIST = [f"{ANNEE}{str(m).zfill(2)}" for m in range(1, 13)] 

def get_csv_urls(api_url, mois):
    r = requests.get(api_url)
    r.raise_for_status()
    data = r.json()
    return [res['url'] for res in data['resources'] if res.get('format', '').lower() == 'csv' and mois in res['url']]

def download_file(url):
    local_filename = url.split('/')[-1]
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

def import_csv_to_db(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = []
        for row in reader:
            rows.append({
                'type': row.get('type'),
                'arrival': row.get('arrival'),
                'headsign': row.get('headsign'),
                'departure': row.get('departure'),
                'arrival_time': row.get('arrival_time'),
                'departure_date': row.get('departure_date'),
                'departure_time': row.get('departure_time')
            })
        if rows:
            supabase.table('trains_supprimes').insert(rows).execute()
            print(f"✅ {len(rows)} lignes insérées depuis {filename}")
        else:
            print(f"Aucune donnée à insérer pour {filename}")

def main():
    all_urls = []
    for mois in MOIS_LIST:
        urls = get_csv_urls(API_URL, mois)
        print(f"{len(urls)} fichiers à traiter pour {mois}.")
        all_urls.extend(urls)
    print(f"Total fichiers à traiter : {len(all_urls)}")
    for url in all_urls:
        print(f"Téléchargement de {url}")
        filename = download_file(url)
        import_csv_to_db(filename)
        os.remove(filename)
        print(f"Fichier {filename} supprimé.")

if __name__ == "__main__":
    main() 