// Dashboard Search Functionality

class SearchForm {
    constructor() {
        this.form = document.getElementById('searchForm');
        this.resultsSection = document.getElementById('resultsSection');
        this.resultsGrid = document.getElementById('resultsGrid');
        this.submitBtn = this.form.querySelector('.btn-go');
        
        // Form inputs
        this.minAge = document.getElementById('minAge');
        this.maxAge = document.getElementById('maxAge');
        this.minValue = document.getElementById('minValue');
        this.maxValue = document.getElementById('maxValue');
        this.position = document.getElementById('position');

        // Stats filter
        this.statsFilterBtn = document.getElementById('statsFilterBtn');
        this.statsFilterModal = document.getElementById('statsFilterModal');
        this.closeStatsModal = document.getElementById('closeStatsModal');
        this.applyStatsBtn = document.getElementById('applyStatsBtn');
        this.selectedStats = ['goals', 'assists', 'keyPasses']; // Default stats

        this.init();
    }

    init() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleSearch(e));

        // Input validation
        this.addInputValidation();

        // Sidebar navigation
        this.initNavigation();

        // Stats filter modal
        this.initStatsFilter();
    }

    initStatsFilter() {
        // Open modal
        this.statsFilterBtn.addEventListener('click', () => {
            this.statsFilterModal.classList.add('show');
        });

        // Close modal
        this.closeStatsModal.addEventListener('click', () => {
            this.statsFilterModal.classList.remove('show');
        });

        // Close on outside click
        this.statsFilterModal.addEventListener('click', (e) => {
            if (e.target === this.statsFilterModal) {
                this.statsFilterModal.classList.remove('show');
            }
        });

        // Apply stats filter
        this.applyStatsBtn.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.stat-checkbox input[type="checkbox"]');
            this.selectedStats = Array.from(checkboxes)
                .filter(cb => cb.checked)
                .map(cb => cb.value);
            
            console.log('Selected stats:', this.selectedStats);
            this.statsFilterModal.classList.remove('show');
            
            // Show success message
            this.showSuccess(`${this.selectedStats.length} stats selected for filtering`);
        });
    }

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-notification';
        successDiv.style.cssText = `
            position: fixed;
            top: 100px;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: rgba(74, 222, 128, 0.2);
            border: 1px solid rgba(74, 222, 128, 0.5);
            border-radius: 12px;
            color: #4ade80;
            font-weight: 600;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        successDiv.textContent = message;
        document.body.appendChild(successDiv);
        setTimeout(() => successDiv.remove(), 3000);
    }

    handleSearch(e) {
        e.preventDefault();

        // Get form values
        const searchParams = {
            minAge: this.minAge.value,
            maxAge: this.maxAge.value,
            minValue: this.minValue.value,
            maxValue: this.maxValue.value,
            position: this.position.value
        };

        // Validate inputs
        if (!this.validateInputs(searchParams)) {
            return;
        }

        // Show loading state
        this.setLoading(true);

        // Call real API
        apiService.searchPlayers(searchParams)
            .then(response => {
                this.setLoading(false);
                
                if (response.success) {
                    console.log('API Response:', response);
                    this.displayResults(response.players);
                } else {
                    this.showError('Failed to fetch players');
                }
            })
            .catch(error => {
                this.setLoading(false);
                console.error('Search error:', error);
                this.showError(error.message || 'Failed to connect to API. Make sure Flask is running on port 5000.');
                
                // Fallback to mock data if API fails
                console.log('Using mock data as fallback...');
                this.displayResults(this.getMockResults(searchParams));
            });
    }

    validateInputs(params) {
        // Check if min age is less than max age
        if (params.minAge && params.maxAge) {
            if (parseInt(params.minAge) > parseInt(params.maxAge)) {
                this.showError('Min Age must be less than Max Age');
                return false;
            }
        }

        // Check if min value is less than max value
        if (params.minValue && params.maxValue) {
            if (parseInt(params.minValue) > parseInt(params.maxValue)) {
                this.showError('Min Value must be less than Max Value');
                return false;
            }
        }

        return true;
    }

    showError(message) {
        // Create error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.style.cssText = `
            position: fixed;
            top: 100px;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: rgba(255, 107, 74, 0.2);
            border: 1px solid rgba(255, 107, 74, 0.5);
            border-radius: 12px;
            color: #ff6b4a;
            font-weight: 600;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        errorDiv.textContent = message;

        document.body.appendChild(errorDiv);

        // Remove after 3 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 3000);

        // Add animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }

    setLoading(loading) {
        if (loading) {
            this.submitBtn.classList.add('loading');
            this.submitBtn.disabled = true;
            this.submitBtn.textContent = 'SEARCHING...';
        } else {
            this.submitBtn.classList.remove('loading');
            this.submitBtn.disabled = false;
            this.submitBtn.textContent = 'GO!';
        }
    }

    getMockResults(params) {
        // Mock data for demonstration
        const mockPlayers = [
            { name: 'João Silva', age: 24, position: 'ST', value: 5000000, nationality: '🇧🇷', team: 'FC Porto' },
            { name: 'Marco Rossi', age: 28, position: 'CM', value: 8000000, nationality: '🇮🇹', team: 'AC Milan' },
            { name: 'Thomas Müller', age: 26, position: 'CAM', value: 12000000, nationality: '🇩🇪', team: 'Bayern Munich' },
            { name: 'Pierre Dubois', age: 22, position: 'CB', value: 6000000, nationality: '🇫🇷', team: 'Lyon' },
            { name: 'Carlos García', age: 25, position: 'RW', value: 7500000, nationality: '🇪🇸', team: 'Barcelona' },
            { name: 'John Smith', age: 27, position: 'CDM', value: 9000000, nationality: '🇬🇧', team: 'Liverpool' },
        ];

        // Filter based on search parameters
        return mockPlayers.filter(player => {
            if (params.minAge && player.age < parseInt(params.minAge)) return false;
            if (params.maxAge && player.age > parseInt(params.maxAge)) return false;
            if (params.minValue && player.value < parseInt(params.minValue)) return false;
            if (params.maxValue && player.value > parseInt(params.maxValue)) return false;
            if (params.position && player.position.toLowerCase() !== params.position.toLowerCase()) return false;
            return true;
        });
    }

    displayResults(players) {
        // Clear previous results
        this.resultsGrid.innerHTML = '';

        if (players.length === 0) {
            this.resultsSection.classList.add('show');
            this.resultsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <div class="empty-state-text">No players found with these criteria</div>
                </div>
            `;
            return;
        }

        // Display results
        this.resultsSection.classList.add('show');
        
        players.forEach((player, index) => {
            const card = this.createPlayerCard(player);
            card.style.animationDelay = `${index * 0.1}s`;
            this.resultsGrid.appendChild(card);
        });

        // Scroll to results
        this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    createPlayerCard(player) {
        const card = document.createElement('div');
        card.className = 'player-card';
        card.style.animation = 'fadeInUp 0.5s ease backwards';

        // Handle different data formats from API vs mock data
        const playerName = player.player_name || player.name || 'Unknown Player';
        const playerTeam = player.club_name || player.team || 'Unknown Club';
        const playerAge = player.age || 'N/A';
        const playerPosition = (player.position || 'N/A').toUpperCase();
        const playerValue = player.price_int || player.value || 0;
        const playerRating = player.rating || 'N/A';
        const playerGoals = player.goals || 0;
        const playerAssists = player.assists || 0;
        const playerKeyPasses = player.key_passes || 0;
        const playerNationality = player.nationality || '⚽';

        // Advanced stats
        const bigChancesCreated = player.big_chances_created || 0;
        const passCompletion = player.pass_completion || 0;
        const tacklesPer90 = player.tackles_per_90 || 0;
        const interceptionsPer90 = player.interceptions_per_90 || 0;
        const dribbledPastPer90 = player.dribbled_past_per_90 || 0;

        // Build stats HTML based on selected stats
        let statsHtml = '';
        
        // Always show basic stats grid
        statsHtml += `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                <div>
                    <p style="color: var(--text-gray); font-size: 0.75rem; margin: 0;">Age</p>
                    <p style="color: #fff; font-weight: 600; margin: 0.25rem 0 0;">${playerAge}</p>
                </div>
                <div>
                    <p style="color: var(--text-gray); font-size: 0.75rem; margin: 0;">Position</p>
                    <p style="color: var(--gradient-green); font-weight: 700; margin: 0.25rem 0 0;">
                        ${playerPosition}
                    </p>
                </div>
            </div>
        `;

        // Build selected stats section
        const selectedStatsData = [];
        
        if (this.selectedStats.includes('goals')) {
            selectedStatsData.push({ label: 'Goals', value: playerGoals, color: '#4ade80' });
        }
        if (this.selectedStats.includes('assists')) {
            selectedStatsData.push({ label: 'Assists', value: playerAssists, color: '#fbbf24' });
        }
        if (this.selectedStats.includes('keyPasses')) {
            selectedStatsData.push({ label: 'Key Passes', value: playerKeyPasses, color: '#60a5fa' });
        }
        if (this.selectedStats.includes('bigChancesCreated')) {
            selectedStatsData.push({ label: 'Big Chances', value: bigChancesCreated, color: '#ec4899' });
        }
        if (this.selectedStats.includes('passCompletion')) {
            selectedStatsData.push({ label: 'Pass %', value: passCompletion + '%', color: '#8b5cf6' });
        }
        if (this.selectedStats.includes('tacklesPer90')) {
            selectedStatsData.push({ label: 'Tackles/90', value: tacklesPer90, color: '#3b82f6' });
        }
        if (this.selectedStats.includes('interceptionsPer90')) {
            selectedStatsData.push({ label: 'Int/90', value: interceptionsPer90, color: '#06b6d4' });
        }
        if (this.selectedStats.includes('dribbledPastPer90')) {
            selectedStatsData.push({ label: 'Drib Past/90', value: dribbledPastPer90, color: '#f97316' });
        }

        // Create stats grid with dynamic columns
        const columns = selectedStatsData.length <= 3 ? selectedStatsData.length : 3;
        statsHtml += `
            <div style="display: grid; grid-template-columns: repeat(${columns}, 1fr); gap: 0.75rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);">
        `;
        
        selectedStatsData.forEach(stat => {
            statsHtml += `
                <div style="text-align: center;">
                    <p style="color: var(--text-gray); font-size: 0.7rem; margin: 0;">${stat.label}</p>
                    <p style="color: ${stat.color}; font-weight: 700; margin: 0.25rem 0 0;">${stat.value !== null ? stat.value : 0}</p>
                </div>
            `;
        });
        
        statsHtml += '</div>';

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                <div style="flex: 1;">
                    <h4 style="font-size: 1.25rem; font-weight: 700; margin: 0 0 0.5rem 0; color: #fff;">
                        ${playerName}
                    </h4>
                    <p style="color: var(--text-gray); margin: 0; font-size: 0.875rem;">
                        ${playerTeam}
                    </p>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 1.5rem; background: rgba(255,255,255,0.1); padding: 0.5rem; border-radius: 8px;">
                        ${playerRating !== 'N/A' && playerRating !== null ? '⭐ ' + playerRating : playerNationality}
                    </span>
                    <button class="add-to-list-btn" data-player='${JSON.stringify(player).replace(/'/g, "&apos;")}' title="Add to list">
                        +
                    </button>
                </div>
            </div>
            ${statsHtml}
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <p style="color: var(--text-gray); font-size: 0.75rem; margin: 0;">Market Value</p>
                <p style="color: var(--accent-color); font-weight: 700; font-size: 1.125rem; margin: 0.25rem 0 0;">
                    €${this.formatCurrency(playerValue)}
                </p>
            </div>
        `;

        // Add list button functionality
        const addBtn = card.querySelector('.add-to-list-btn');
        addBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showAddToListMenu(player, addBtn);
        });

        // Add click event
        card.addEventListener('click', () => {
            this.showPlayerDetails(player);
        });

        return card;
    }

    showAddToListMenu(player, button) {
        // Remove any existing menus
        document.querySelectorAll('.add-to-list-menu').forEach(m => m.remove());

        const lists = JSON.parse(localStorage.getItem('playerLists')) || {};
        const menu = document.createElement('div');
        menu.className = 'add-to-list-menu';
        
        const rect = button.getBoundingClientRect();
        menu.style.cssText = `
            position: fixed;
            top: ${rect.bottom + 10}px;
            left: ${rect.left - 150}px;
            background: rgba(26, 41, 66, 0.98);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 0.5rem;
            min-width: 200px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 2000;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
            animation: fadeIn 0.2s ease;
        `;

        if (Object.keys(lists).length === 0) {
            menu.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: var(--text-gray);">
                    <p style="margin: 0 0 0.5rem 0;">No lists yet</p>
                    <button class="create-first-list-btn" style="
                        padding: 0.5rem 1rem;
                        background: var(--gradient-green);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 600;
                    ">Create List</button>
                </div>
            `;
            menu.querySelector('.create-first-list-btn').addEventListener('click', () => {
                window.location.href = 'lists.html';
            });
        } else {
            let menuHTML = '<div style="padding: 0.5rem;">';
            menuHTML += '<p style="color: var(--text-gray); font-size: 0.85rem; margin: 0 0 0.5rem 0; padding: 0 0.5rem;">Add to list:</p>';
            
            Object.values(lists).forEach(list => {
                menuHTML += `
                    <button class="list-menu-item" data-list-id="${list.id}" style="
                        width: 100%;
                        padding: 0.75rem;
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 8px;
                        color: white;
                        text-align: left;
                        cursor: pointer;
                        margin-bottom: 0.5rem;
                        transition: all 0.2s ease;
                    ">
                        <div style="font-weight: 600;">${list.name}</div>
                        <div style="font-size: 0.8rem; color: var(--text-gray);">${list.players.length} players</div>
                    </button>
                `;
            });
            
            menuHTML += '</div>';
            menu.innerHTML = menuHTML;

            // Add click handlers
            menu.querySelectorAll('.list-menu-item').forEach(item => {
                item.addEventListener('mouseenter', () => {
                    item.style.background = 'rgba(74, 222, 128, 0.1)';
                    item.style.borderColor = 'var(--gradient-green)';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.background = 'rgba(255, 255, 255, 0.05)';
                    item.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                });
                item.addEventListener('click', () => {
                    const listId = item.dataset.listId;
                    this.addPlayerToList(player, listId);
                    menu.remove();
                });
            });
        }

        document.body.appendChild(menu);

        // Close menu when clicking outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target) && e.target !== button) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    }

    addPlayerToList(player, listId) {
        const lists = JSON.parse(localStorage.getItem('playerLists')) || {};
        
        if (!lists[listId]) {
            this.showError('List not found');
            return;
        }

        const list = lists[listId];
        
        // Check if player already exists
        const exists = list.players.some(p => (p.player_id || p.id) === (player.player_id || player.id));
        
        if (exists) {
            this.showError('Player already in this list');
            return;
        }

        list.players.push(player);
        localStorage.setItem('playerLists', JSON.stringify(lists));

        this.showSuccess(`Added to "${list.name}"`);
    }

    formatCurrency(value) {
        if (!value || value === 0) return '0';
        
        if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (value >= 1000) {
            return (value / 1000).toFixed(0) + 'K';
        }
        return value.toString();
    }

    showPlayerDetails(player) {
        // Create modal or redirect to player page
        console.log('Show details for:', player);
        // You can implement a modal or navigation here
    }

    showAddToListMenu(player, button) {
        // Remove any existing menus
        document.querySelectorAll('.add-to-list-menu').forEach(m => m.remove());

        const lists = JSON.parse(localStorage.getItem('playerLists')) || {};
        console.log('Available lists:', lists); // Debug log
        const menu = document.createElement('div');
        menu.className = 'add-to-list-menu';
        
        const rect = button.getBoundingClientRect();
        menu.style.cssText = `
            position: fixed;
            top: ${rect.bottom + 10}px;
            left: ${rect.left - 150}px;
            background: rgba(26, 41, 66, 0.98);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 0.5rem;
            min-width: 200px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 2000;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
            animation: fadeIn 0.2s ease;
        `;

        if (Object.keys(lists).length === 0) {
            menu.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: var(--text-gray);">
                    <p style="margin: 0 0 0.5rem 0;">No lists yet</p>
                    <button class="create-first-list-btn" style="
                        padding: 0.5rem 1rem;
                        background: var(--gradient-green);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 600;
                    ">Create List</button>
                </div>
            `;
            menu.querySelector('.create-first-list-btn').addEventListener('click', () => {
                window.location.href = 'lists.html';
            });
        } else {
            let menuHTML = '<div style="padding: 0.5rem;">';
            menuHTML += '<p style="color: var(--text-gray); font-size: 0.85rem; margin: 0 0 0.5rem 0; padding: 0 0.5rem;">Add to list:</p>';
            
            Object.values(lists).forEach(list => {
                menuHTML += `
                    <button class="list-menu-item" data-list-id="${list.id}" style="
                        width: 100%;
                        padding: 0.75rem;
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 8px;
                        color: white;
                        text-align: left;
                        cursor: pointer;
                        margin-bottom: 0.5rem;
                        transition: all 0.2s ease;
                    ">
                        <div style="font-weight: 600;">${list.name}</div>
                        <div style="font-size: 0.8rem; color: var(--text-gray);">${list.players.length} players</div>
                    </button>
                `;
            });
            
            menuHTML += '</div>';
            menu.innerHTML = menuHTML;

            // Add click handlers
            menu.querySelectorAll('.list-menu-item').forEach(item => {
                item.addEventListener('mouseenter', () => {
                    item.style.background = 'rgba(74, 222, 128, 0.1)';
                    item.style.borderColor = 'var(--gradient-green)';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.background = 'rgba(255, 255, 255, 0.05)';
                    item.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                });
                item.addEventListener('click', () => {
                    const listId = item.dataset.listId;
                    this.addPlayerToList(player, listId);
                    menu.remove();
                });
            });
        }

        document.body.appendChild(menu);

        // Close menu when clicking outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target) && e.target !== button) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    }

    addPlayerToList(player, listId) {
        const lists = JSON.parse(localStorage.getItem('playerLists')) || {};
        
        if (!lists[listId]) {
            this.showError('List not found');
            return;
        }

        const list = lists[listId];
        
        // Check if player already exists
        const exists = list.players.some(p => (p.player_id || p.id) === (player.player_id || player.id));
        
        if (exists) {
            this.showError('Player already in this list');
            return;
        }

        list.players.push(player);
        localStorage.setItem('playerLists', JSON.stringify(lists));

        this.showSuccess(`Added to "${list.name}"`);
    }

    addInputValidation() {
        // Prevent negative values
        const numberInputs = [this.minAge, this.maxAge, this.minValue, this.maxValue];
        
        numberInputs.forEach(input => {
            input.addEventListener('input', () => {
                if (input.value < 0) {
                    input.value = 0;
                }
            });
        });

        // Format value inputs to show currency
        [this.minValue, this.maxValue].forEach(input => {
            input.addEventListener('blur', () => {
                if (input.value) {
                    const value = parseInt(input.value);
                    input.value = value;
                }
            });
        });
    }

    initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const href = item.getAttribute('href');

            // ✅ Only block navigation for internal anchors (like "#lineups")
            if (href && href.startsWith('#')) {
                e.preventDefault();
                console.log('Navigating internally to:', href);
            } else {
                // Let the browser handle normal navigation (like lists.html)
                return;
            }

            // Remove active class from all items
            navItems.forEach(nav => nav.classList.remove('active'));

            // Add active class to clicked item
            item.classList.add('active');

            // Handle in-page sections if needed
            if (href === '#lineups') {
                // your in-dashboard navigation logic
                console.log('Open lineups section');
            }
        });
    });
}
}

// Sidebar Toggle for Mobile
class SidebarToggle {
    constructor() {
        this.sidebar = document.querySelector('.sidebar');
        this.createToggleButton();
    }

    createToggleButton() {
        const button = document.createElement('button');
        button.className = 'sidebar-toggle';
        button.innerHTML = '☰';
        button.style.cssText = `
            position: fixed;
            top: 1.5rem;
            left: 1rem;
            z-index: 1001;
            background: rgba(26, 41, 66, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            width: 45px;
            height: 45px;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        `;

        button.addEventListener('click', () => {
            this.sidebar.classList.toggle('open');
            button.innerHTML = this.sidebar.classList.contains('open') ? '✕' : '☰';
        });

        document.body.appendChild(button);

        // Show toggle button on mobile
        const mediaQuery = window.matchMedia('(max-width: 768px)');
        const handleResize = (e) => {
            button.style.display = e.matches ? 'flex' : 'none';
            if (!e.matches) {
                this.sidebar.classList.remove('open');
                button.innerHTML = '☰';
            }
        };

        mediaQuery.addListener(handleResize);
        handleResize(mediaQuery);

        // Close sidebar when clicking outside
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768) {
                if (!this.sidebar.contains(e.target) && !button.contains(e.target)) {
                    this.sidebar.classList.remove('open');
                    button.innerHTML = '☰';
                }
            }
        });
    }
}

// Enhanced Input Effects
class InputAnimations {
    constructor() {
        this.init();
    }

    init() {
        const inputs = document.querySelectorAll('.form-input, .form-select');
        
        inputs.forEach(input => {
            // Add floating effect
            input.addEventListener('focus', () => {
                input.parentElement.style.transform = 'scale(1.01)';
                input.parentElement.style.transition = 'transform 0.2s ease';
            });

            input.addEventListener('blur', () => {
                input.parentElement.style.transform = 'scale(1)';
            });

            // Add ripple effect on focus
            input.addEventListener('focus', (e) => {
                this.createRipple(e);
            });
        });
    }

    createRipple(e) {
        const input = e.currentTarget;
        const rect = input.getBoundingClientRect();
        
        const ripple = document.createElement('span');
        ripple.style.cssText = `
            position: absolute;
            border-radius: 50%;
            background: rgba(74, 222, 128, 0.3);
            width: 20px;
            height: 20px;
            left: ${e.clientX - rect.left - 10}px;
            top: ${e.clientY - rect.top - 10}px;
            pointer-events: none;
            animation: rippleEffect 0.6s ease-out;
        `;

        input.parentElement.style.position = 'relative';
        input.parentElement.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    }
}

// Position Badge Styling
class PositionBadges {
    constructor() {
        this.positionColors = {
            'cb': '#3b82f6',
            'rb': '#06b6d4',
            'lb': '#06b6d4',
            'cdm': '#8b5cf6',
            'cm': '#a855f7',
            'cam': '#ec4899',
            'rw': '#f59e0b',
            'lw': '#f59e0b',
            'st': '#ef4444',
            'ss': '#f97316'
        };
    }

    getColor(position) {
        return this.positionColors[position.toLowerCase()] || '#4ade80';
    }
}

// Keyboard Shortcuts
class KeyboardShortcuts {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus on first input
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('minAge').focus();
            }

            // Ctrl/Cmd + Enter to submit form
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('searchForm').dispatchEvent(new Event('submit'));
            }

            // Escape to clear results
            if (e.key === 'Escape') {
                const resultsSection = document.getElementById('resultsSection');
                if (resultsSection.classList.contains('show')) {
                    resultsSection.classList.remove('show');
                }
            }
        });
    }
}

// Auto-save form data
class FormAutoSave {
    constructor() {
        this.form = document.getElementById('searchForm');
        this.init();
    }

    init() {
        // Load saved data on page load
        this.loadFormData();

        // Save data on input change
        const inputs = this.form.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('change', () => {
                this.saveFormData();
            });
        });
    }

    saveFormData() {
        const formData = {
            minAge: document.getElementById('minAge').value,
            maxAge: document.getElementById('maxAge').value,
            minValue: document.getElementById('minValue').value,
            maxValue: document.getElementById('maxValue').value,
            position: document.getElementById('position').value
        };

        // Store in memory (not localStorage as per instructions)
        window.savedSearchFormData = formData;
    }

    loadFormData() {
        const savedData = window.savedSearchFormData;
        
        if (savedData) {
            document.getElementById('minAge').value = savedData.minAge || '';
            document.getElementById('maxAge').value = savedData.maxAge || '';
            document.getElementById('minValue').value = savedData.minValue || '';
            document.getElementById('maxValue').value = savedData.maxValue || '';
            document.getElementById('position').value = savedData.position || '';
        }
    }
}

// Initialize all dashboard features
document.addEventListener('DOMContentLoaded', () => {
    new SearchForm();
    new SidebarToggle();
    new InputAnimations();
    new PositionBadges();
    new KeyboardShortcuts();
    new FormAutoSave();

    // Add loaded class
    document.body.classList.add('loaded');

    console.log('Dashboard initialized successfully! 🚀');
    console.log('Keyboard shortcuts:');
    console.log('- Ctrl/Cmd + K: Focus on search');
    console.log('- Ctrl/Cmd + Enter: Submit search');
    console.log('- Escape: Close results');
});