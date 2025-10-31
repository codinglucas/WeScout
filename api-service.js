// API Service for WeScout
// Configure your API base URL here
const API_BASE_URL = 'http://localhost:5000/api';

class APIService {
    constructor() {
        this.baseURL = API_BASE_URL;
    }

    /**
     * Search players with filters
     * @param {Object} params - Search parameters
     * @returns {Promise} API response
     */
    async searchPlayers(params) {
        try {
            // Build query string
            const queryParams = new URLSearchParams();
            
            if (params.minAge) queryParams.append('min_age', params.minAge);
            if (params.maxAge) queryParams.append('max_age', params.maxAge);
            if (params.minValue) queryParams.append('min_value', params.minValue);
            if (params.maxValue) queryParams.append('max_value', params.maxValue);
            if (params.position) queryParams.append('position', params.position);

            const url = `${this.baseURL}/players/search?${queryParams.toString()}`;
            
            console.log('Fetching from:', url);

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch players');
            }

            const data = await response.json();
            return data;

        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    /**
     * Get all available positions
     * @returns {Promise} List of positions
     */
    async getPositions() {
        try {
            const response = await fetch(`${this.baseURL}/positions`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error('Failed to fetch positions');
            }

            const data = await response.json();
            return data.positions;

        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    /**
     * Health check
     * @returns {Promise} API status
     */
    async healthCheck() {
        try {
            const response = await fetch(`${this.baseURL}/health`, {
                method: 'GET',
            });

            const data = await response.json();
            return data;

        } catch (error) {
            console.error('API Health Check Failed:', error);
            return { success: false, error: error.message };
        }
    }
}

// Export singleton instance
const apiService = new APIService();