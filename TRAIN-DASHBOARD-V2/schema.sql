-- Schéma de la base de données pour le Dashboard Trains Supprimés V2 (sans colonne motif)

-- Supprimer la table si elle existe
DROP TABLE IF EXISTS trains_supprimes;

-- Créer la table trains_supprimes avec les champs du CSV
CREATE TABLE trains_supprimes (
    id BIGSERIAL PRIMARY KEY,
    type TEXT,
    arrival TEXT,
    headsign TEXT,
    departure TEXT,
    arrival_time TIMESTAMP,
    departure_date DATE,
    departure_time TIMESTAMP
);

-- Activer Row Level Security (RLS)
ALTER TABLE trains_supprimes ENABLE ROW LEVEL SECURITY;

-- Créer une politique pour permettre la lecture publique
CREATE POLICY "Permettre lecture publique" ON trains_supprimes
    FOR SELECT USING (true);

-- Créer une politique pour permettre l'insertion avec la clé de service
CREATE POLICY "Permettre insertion service" ON trains_supprimes
    FOR INSERT WITH CHECK (true);

-- Créer une politique pour permettre la mise à jour avec la clé de service
CREATE POLICY "Permettre mise à jour service" ON trains_supprimes
    FOR UPDATE USING (true);

-- Créer une politique pour permettre la suppression avec la clé de service
CREATE POLICY "Permettre suppression service" ON trains_supprimes
    FOR DELETE USING (true); 