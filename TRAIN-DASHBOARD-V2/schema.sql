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

-- Quelques lignes d'exemple
INSERT INTO trains_supprimes (type, arrival, headsign, departure, arrival_time, departure_date, departure_time) VALUES
('TER', 'Paris Gare de Lyon', '876543', 'Lyon Part-Dieu', '2023-06-01 10:45:00', '2023-06-01', '2023-06-01 08:30:00'),
('TGV', 'Marseille St-Charles', '123456', 'Paris Gare de Lyon', '2023-06-02 15:00:00', '2023-06-02', '2023-06-02 12:00:00'),
('TER', 'Bordeaux', '654321', 'Toulouse', '2023-06-03 18:20:00', '2023-06-03', '2023-06-03 16:00:00');

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