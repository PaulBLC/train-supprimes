// Configuration
const API_BASE = '/api';
let currentOffset = 0;
const LIMIT = 50;

// Éléments DOM
const trainsTable = document.getElementById('trains-table');
const trainsTbody = document.getElementById('trains-tbody');
const totalTrainsEl = document.getElementById('total-trains');
const dateLimiteEl = document.getElementById('date-limite');
const statusEl = document.getElementById('status');
const refreshBtn = document.getElementById('refresh-btn');
const loadMoreBtn = document.getElementById('load-more-btn');
const loadingEl = document.getElementById('loading');

// Événements
refreshBtn.addEventListener('click', loadData);
loadMoreBtn.addEventListener('click', loadMoreData);

// Ajout d'un champ de filtre date
const filterDateInput = document.createElement('input');
filterDateInput.type = 'date';
filterDateInput.id = 'filter-date';
filterDateInput.className = 'filter-date';
filterDateInput.style.marginRight = '1em';
filterDateInput.addEventListener('change', () => {
    loadData();
});
const controlsDiv = document.querySelector('.controls');
controlsDiv.insertBefore(filterDateInput, controlsDiv.firstChild);

// Fonctions principales
async function loadData() {
    showLoading(true);
    currentOffset = 0;
    
    try {
        // Charger les statistiques
        await loadStats();
        
        // Charger les données des trains
        await loadTrainsData();
        
    } catch (error) {
        console.error('Erreur lors du chargement:', error);
        showError('Erreur lors du chargement des données');
    } finally {
        showLoading(false);
    }
}

async function loadMoreData() {
    showLoading(true);
    currentOffset += LIMIT;
    
    try {
        await loadTrainsData(true); // append = true
    } catch (error) {
        console.error('Erreur lors du chargement:', error);
        showError('Erreur lors du chargement des données');
        currentOffset -= LIMIT; // Revenir à l'offset précédent
    } finally {
        showLoading(false);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        if (data.success) {
            totalTrainsEl.textContent = data.data.total_trains.toLocaleString();
            dateLimiteEl.textContent = new Date().toLocaleDateString('fr-FR');
        }
        
        // Vérifier la santé de l'API
        const healthResponse = await fetch(`${API_BASE}/health`);
        const healthData = await healthResponse.json();
        
        if (healthData.status === 'healthy') {
            statusEl.textContent = '✅ Connecté';
            statusEl.className = 'stat-value status-healthy';
        } else {
            statusEl.textContent = '❌ Erreur';
            statusEl.className = 'stat-value status-unhealthy';
        }
        
    } catch (error) {
        console.error('Erreur lors du chargement des stats:', error);
        statusEl.textContent = '❌ Erreur';
        statusEl.className = 'stat-value status-unhealthy';
    }
}

async function loadTrainsData(append = false) {
    try {
        const params = new URLSearchParams({
            limit: LIMIT,
            offset: currentOffset
        });
        const filterDate = document.getElementById('filter-date').value;
        if (filterDate) {
            params.append('departure_date', filterDate);
        }
        const response = await fetch(`${API_BASE}/trains?${params}`);
        const data = await response.json();
        
        if (data.success) {
            if (!append) {
                // Vider le tableau si c'est un nouveau chargement
                trainsTbody.innerHTML = '';
            }
            
            if (data.data.length === 0) {
                if (!append) {
                    trainsTbody.innerHTML = '<tr><td colspan="7" class="loading">Aucune donnée disponible</td></tr>';
                }
                loadMoreBtn.disabled = true;
                return;
            }
            
            // Ajouter les données au tableau
            data.data.forEach(train => {
                const row = createTrainRow(train);
                trainsTbody.appendChild(row);
            });
            
            // Désactiver le bouton "Charger plus" si on a moins de LIMIT résultats
            if (data.data.length < LIMIT) {
                loadMoreBtn.disabled = true;
            } else {
                loadMoreBtn.disabled = false;
            }
            
        } else {
            throw new Error(data.error || 'Erreur inconnue');
        }
        
    } catch (error) {
        console.error('Erreur lors du chargement des trains:', error);
        if (!append) {
            trainsTbody.innerHTML = '<tr><td colspan="7" class="loading">Erreur lors du chargement</td></tr>';
        }
        throw error;
    }
}

function createTrainRow(train) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${train.type || '-'}</td>
        <td>${train.arrival || '-'}</td>
        <td>${train.headsign || '-'}</td>
        <td>${train.departure || '-'}</td>
        <td>${formatTime(train.arrival_time)}</td>
        <td>${formatDate(train.departure_date)}</td>
        <td>${formatTime(train.departure_time)}</td>
    `;
    return row;
}

function formatTime(dt) {
    if (!dt) return '-';
    try {
        const d = new Date(dt);
        if (!isNaN(d)) {
            return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        }
        if (/^\d{2}:\d{2}/.test(dt)) return dt;
        return dt;
    } catch {
        return dt;
    }
}

function formatDate(dt) {
    if (!dt) return '-';
    try {
        const d = new Date(dt);
        if (!isNaN(d)) {
            return d.toLocaleDateString('fr-FR');
        }
        if (/^\d{2}\/\d{2}\/\d{4}/.test(dt)) return dt;
        if (/^\d{4}-\d{2}-\d{2}/.test(dt)) {
            // format YYYY-MM-DD
            const [y, m, d2] = dt.split('-');
            return `${d2}/${m}/${y}`;
        }
        return dt;
    } catch {
        return dt;
    }
}

function showLoading(show) {
    if (show) {
        loadingEl.style.display = 'block';
        refreshBtn.disabled = true;
        loadMoreBtn.disabled = true;
    } else {
        loadingEl.style.display = 'none';
        refreshBtn.disabled = false;
        loadMoreBtn.disabled = false;
    }
}

function showError(message) {
    trainsTbody.innerHTML = `<tr><td colspan="7" class="loading" style="color: #dc3545;">${message}</td></tr>`;
}

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

// Auto-refresh toutes les 5 minutes
setInterval(() => {
    loadStats();
}, 5 * 60 * 1000); 