// Lists Management System

class ListsManager {
    constructor() {
        // Load lists from localStorage or use empty object
        this.lists = JSON.parse(localStorage.getItem('playerLists')) || {};
        this.currentListId = null;

        // DOM elements
        this.listsNav = document.getElementById('listsNav');
        this.playersGrid = document.getElementById('playersGrid');
        this.emptyState = document.getElementById('emptyState');
        this.currentListName = document.getElementById('currentListName');
        this.currentListCount = document.getElementById('currentListCount');

        // Buttons
        this.createListBtn = document.getElementById('createListBtn');
        this.renameListBtn = document.getElementById('renameListBtn');
        this.deleteListBtn = document.getElementById('deleteListBtn');

        // Modals
        this.createListModal = document.getElementById('createListModal');
        this.renameListModal = document.getElementById('renameListModal');
        this.deleteConfirmModal = document.getElementById('deleteConfirmModal');

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.renderListsNav();
        this.checkEmptyState();
    }

    saveLists() {
        localStorage.setItem('playerLists', JSON.stringify(this.lists));
    }

    setupEventListeners() {
        // Create list
        this.createListBtn.addEventListener('click', () => this.openCreateModal());
        document.getElementById('confirmCreateBtn').addEventListener('click', () => this.createList());
        document.getElementById('cancelCreateBtn').addEventListener('click', () => this.closeModal('create'));
        document.getElementById('closeCreateModal').addEventListener('click', () => this.closeModal('create'));

        // Rename list
        this.renameListBtn.addEventListener('click', () => this.openRenameModal());
        document.getElementById('confirmRenameBtn').addEventListener('click', () => this.renameList());
        document.getElementById('cancelRenameBtn').addEventListener('click', () => this.closeModal('rename'));
        document.getElementById('closeRenameModal').addEventListener('click', () => this.closeModal('rename'));

        // Delete list
        this.deleteListBtn.addEventListener('click', () => this.openDeleteModal());
        document.getElementById('confirmDeleteBtn').addEventListener('click', () => this.deleteList());
        document.getElementById('cancelDeleteBtn').addEventListener('click', () => this.closeModal('delete'));
        document.getElementById('closeDeleteModal').addEventListener('click', () => this.closeModal('delete'));

        // Close modals on outside click
        [this.createListModal, this.renameListModal, this.deleteConfirmModal].forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                }
            });
        });

        // Enter key to submit in modals
        document.getElementById('newListName').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.createList();
        });
        document.getElementById('renameListName').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.renameList();
        });
    }

    openCreateModal() {
        this.createListModal.classList.add('show');
        document.getElementById('newListName').value = '';
        document.getElementById('newListName').focus();
    }

    openRenameModal() {
        if (!this.currentListId) {
            this.showNotification('Please select a list first', 'error');
            return;
        }
        this.renameListModal.classList.add('show');
        document.getElementById('renameListName').value = this.lists[this.currentListId].name;
        document.getElementById('renameListName').focus();
    }

    openDeleteModal() {
        if (!this.currentListId) {
            this.showNotification('Please select a list first', 'error');
            return;
        }
        this.deleteConfirmModal.classList.add('show');
    }

    closeModal(type) {
        if (type === 'create') {
            this.createListModal.classList.remove('show');
        } else if (type === 'rename') {
            this.renameListModal.classList.remove('show');
        } else if (type === 'delete') {
            this.deleteConfirmModal.classList.remove('show');
        }
    }

    createList() {
        const nameInput = document.getElementById('newListName');
        const name = nameInput.value.trim();

        if (!name) {
            this.showNotification('Please enter a list name', 'error');
            return;
        }

        const listId = 'list_' + Date.now();
        this.lists[listId] = {
            id: listId,
            name: name,
            players: [],
            createdAt: new Date().toISOString()
        };

        this.saveLists();
        this.renderListsNav();
        this.selectList(listId);
        this.closeModal('create');
        this.showNotification(`List "${name}" created successfully`, 'success');
    }

    renameList() {
        const nameInput = document.getElementById('renameListName');
        const newName = nameInput.value.trim();

        if (!newName) {
            this.showNotification('Please enter a list name', 'error');
            return;
        }

        this.lists[this.currentListId].name = newName;
        this.saveLists();
        this.renderListsNav();
        this.currentListName.textContent = newName;
        this.closeModal('rename');
        this.showNotification('List renamed successfully', 'success');
    }

    deleteList() {
        const listName = this.lists[this.currentListId].name;
        delete this.lists[this.currentListId];
        this.currentListId = null;

        this.saveLists();
        this.renderListsNav();
        this.checkEmptyState();
        this.closeModal('delete');
        this.showNotification(`List "${listName}" deleted`, 'success');
    }

    selectList(listId) {
        this.currentListId = listId;
        const list = this.lists[listId];

        // Update UI
        this.currentListName.textContent = list.name;
        this.currentListCount.textContent = `${list.players.length} player${list.players.length !== 1 ? 's' : ''}`;

        // Update active state in nav
        document.querySelectorAll('.list-nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.listId === listId);
        });

        // Render players
        this.renderPlayers();
        this.checkEmptyState();
    }

    renderListsNav() {
        this.listsNav.innerHTML = '';

        Object.values(this.lists).forEach(list => {
            const item = document.createElement('div');
            item.className = 'list-nav-item';
            item.dataset.listId = list.id;

            if (list.id === this.currentListId) {
                item.classList.add('active');
            }

            item.innerHTML = `
                <h3 class="list-nav-title">${list.name}</h3>
                <p class="list-nav-count">${list.players.length} player${list.players.length !== 1 ? 's' : ''}</p>
            `;

            item.addEventListener('click', () => this.selectList(list.id));
            this.listsNav.appendChild(item);
        });
    }

    renderPlayers() {
        if (!this.currentListId) {
            this.playersGrid.innerHTML = '';
            return;
        }

        const list = this.lists[this.currentListId];
        this.playersGrid.innerHTML = '';

        list.players.forEach(player => {
            const card = this.createFullPlayerCard(player);
            this.playersGrid.appendChild(card);
        });
    }

    createFullPlayerCard(player) {
        const card = document.createElement('div');
        card.className = 'list-player-card';

        const playerName = player.player_name || player.name || 'Unknown';
        const playerTeam = player.club_name || player.team || 'Unknown';
        const playerPosition = (player.position || 'N/A').toUpperCase();
        const playerRating = player.rating || 'N/A';
        const playerValue = player.price_int || player.value || 0;

        card.innerHTML = `
            <button class="remove-player-btn" data-player-id="${player.player_id || player.id}">✕</button>
            
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                <div>
                    <h4 style="font-size: 1.25rem; font-weight: 700; margin: 0 0 0.5rem 0; color: #fff;">
                        ${playerName}
                    </h4>
                    <p style="color: var(--text-gray); margin: 0; font-size: 0.875rem;">
                        ${playerTeam}
                    </p>
                </div>
                <span style="font-size: 1.5rem; background: rgba(255,255,255,0.1); padding: 0.5rem; border-radius: 8px;">
                    ${playerRating !== 'N/A' && playerRating !== null ? '⭐ ' + playerRating : '⚽'}
                </span>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                <div style="text-align: center; background: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 8px;">
                    <p style="color: var(--text-gray); font-size: 0.75rem; margin: 0;">Position</p>
                    <p style="color: var(--gradient-green); font-weight: 700; margin: 0.25rem 0 0; font-size: 1.125rem;">
                        ${playerPosition}
                    </p>
                </div>
                <div style="text-align: center; background: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 8px;">
                    <p style="color: var(--text-gray); font-size: 0.75rem; margin: 0;">Value</p>
                    <p style="color: var(--accent-color); font-weight: 700; margin: 0.25rem 0 0; font-size: 1.125rem;">
                        €${this.formatCurrency(playerValue)}
                    </p>
                </div>
            </div>

            <div class="all-stats-grid">
                <div class="stat-item">
                    <p class="stat-label">Goals</p>
                    <p class="stat-value" style="color: #4ade80;">${player.goals || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Assists</p>
                    <p class="stat-value" style="color: #fbbf24;">${player.assists || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Key Passes</p>
                    <p class="stat-value" style="color: #60a5fa;">${player.key_passes || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Big Chances</p>
                    <p class="stat-value" style="color: #ec4899;">${player.big_chances_created || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Pass %</p>
                    <p class="stat-value" style="color: #8b5cf6;">${player.pass_completion || 0}%</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Tackles/90</p>
                    <p class="stat-value" style="color: #3b82f6;">${player.tackles_per_90 || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Int/90</p>
                    <p class="stat-value" style="color: #06b6d4;">${player.interceptions_per_90 || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Drib Past/90</p>
                    <p class="stat-value" style="color: #f97316;">${player.dribbled_past_per_90 || 0}</p>
                </div>
                <div class="stat-item">
                    <p class="stat-label">Minutes</p>
                    <p class="stat-value" style="color: #a855f7;">${player.minutes_played || 0}</p>
                </div>
            </div>
        `;

        // Add remove button functionality
        const removeBtn = card.querySelector('.remove-player-btn');
        removeBtn.addEventListener('click', () => {
            this.removePlayer(player.player_id || player.id);
        });

        return card;
    }

    removePlayer(playerId) {
        if (!this.currentListId) return;

        const list = this.lists[this.currentListId];
        list.players = list.players.filter(p => (p.player_id || p.id) !== playerId);

        this.saveLists();
        this.renderPlayers();
        this.renderListsNav();
        this.currentListCount.textContent = `${list.players.length} player${list.players.length !== 1 ? 's' : ''}`;
        this.showNotification('Player removed from list', 'success');
    }

    addPlayerToList(player, listId) {
        if (!this.lists[listId]) {
            this.showNotification('List not found', 'error');
            return;
        }

        const list = this.lists[listId];
        
        // Check if player already exists in list
        const exists = list.players.some(p => (p.player_id || p.id) === (player.player_id || player.id));
        
        if (exists) {
            this.showNotification('Player already in this list', 'error');
            return;
        }

        list.players.push(player);
        this.saveLists();
        this.renderListsNav();

        if (this.currentListId === listId) {
            this.renderPlayers();
            this.currentListCount.textContent = `${list.players.length} player${list.players.length !== 1 ? 's' : ''}`;
        }

        this.showNotification(`Added to "${list.name}"`, 'success');
    }

    formatCurrency(value) {
        if (!value || value === 0 || isNaN(value)) return '0';
        
        if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (value >= 1000) {
            return (value / 1000).toFixed(0) + 'K';
        }
        return value.toString();
    }

    checkEmptyState() {
        if (!this.currentListId) {
            this.emptyState.style.display = 'block';
            this.playersGrid.style.display = 'none';
            this.renameListBtn.style.display = 'none';
            this.deleteListBtn.style.display = 'none';
        } else {
            this.emptyState.style.display = 'none';
            this.playersGrid.style.display = 'grid';
            this.renameListBtn.style.display = 'block';
            this.deleteListBtn.style.display = 'block';
        }
    }

    saveLists() {
        localStorage.setItem('playerLists', JSON.stringify(this.lists));
    }

    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: ${type === 'success' ? 'rgba(74, 222, 128, 0.2)' : 'rgba(255, 107, 74, 0.2)'};
            border: 1px solid ${type === 'success' ? 'rgba(74, 222, 128, 0.5)' : 'rgba(255, 107, 74, 0.5)'};
            border-radius: 12px;
            color: ${type === 'success' ? '#4ade80' : '#ff6b4a'};
            font-weight: 600;
            z-index: 3000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }
}

// Initialize lists manager
let listsManager;
document.addEventListener('DOMContentLoaded', () => {
    listsManager = new ListsManager();
    console.log('Lists Manager initialized! 📋');
});