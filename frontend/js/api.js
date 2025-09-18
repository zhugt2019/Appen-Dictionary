// frontend/js/api.js (Updated Version with Auto-Refresh)

import { state, setAuthState } from './state.js';
import { showLoginModal } from './ui.js';

// A flag to prevent multiple concurrent refresh attempts
let isRefreshing = false;
// A queue for requests that arrive while the token is being refreshed
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

export class API {
    constructor() {
        this.baseURL = ""; 
    }

    _getHeaders(isFormData = false) {
        const headers = { 'Accept': 'application/json' };
        if (state.authToken) {
            headers['Authorization'] = `Bearer ${state.authToken}`;
        }
        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }
        return headers;
    }

    async _handleResponse(response) {
        if (response.ok) {
            if (response.status === 204) return null;
            const text = await response.text();
            try { return JSON.parse(text); } catch (err) { return text; }
        }
        let errorMessage = `API Error: ${response.status}`;
        try {
            const errorData = await response.json();
            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        } catch (error) { /* Ignore if error response is not JSON */ }
        throw new Error(errorMessage);
    }

    // --- NEW: Token Refresh Logic ---
    async _refreshToken() {
        try {
            const response = await this._request('/api/refresh', {
                method: 'POST',
                headers: this._getHeaders(),
                body: JSON.stringify({ refresh_token: state.refreshToken })
            });
            // Update the state with the new access token
            setAuthState(true, response.access_token, state.refreshToken, state.username);
            return response.access_token;
        } catch (error) {
            console.error("Failed to refresh token", error);
            // If refresh fails, the session is truly over. Log out.
            setAuthState(false, null, null, null);
            showLoginModal(); // Prompt user to log in again
            return Promise.reject(error);
        }
    }

    // --- MODIFIED: The core request function with retry logic ---
    async _request(endpoint, options) {
        try {
            // Add the current auth token to the headers for the initial request
            options.headers = this._getHeaders('body' in options && options.body instanceof FormData);
            const response = await fetch(`${this.baseURL}${endpoint}`, options);
            
            // If the response is not 401, handle it normally
            if (response.status !== 401) {
                return await this._handleResponse(response);
            }

            // --- Handle 401 Unauthorized Error ---

            // If we are already refreshing, add this request to the queue
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                })
                .then(newAccessToken => {
                    options.headers['Authorization'] = `Bearer ${newAccessToken}`;
                    return this._request(endpoint, options); // Retry with the new token
                });
            }

            isRefreshing = true;

            return this._refreshToken()
                .then(newAccessToken => {
                    processQueue(null, newAccessToken); // Process queued requests successfully
                    options.headers['Authorization'] = `Bearer ${newAccessToken}`;
                    // Retry the original failed request with the new token
                    return fetch(`${this.baseURL}${endpoint}`, options).then(this._handleResponse);
                })
                .catch(err => {
                    processQueue(err, null); // Reject queued requests
                    return Promise.reject(err);
                })
                .finally(() => {
                    isRefreshing = false;
                });

        } catch (error) {
            console.error(`API request to ${endpoint} failed:`, error);
            throw error;
        }
    }
    
    // --- Authentication Methods (login response now contains refresh_token) ---
    async register(username, password) {
        return this._request('/api/register', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    }

    async login(username, password) {
        // This initial login should not use the retry logic
        const response = await fetch(`${this.baseURL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        return await this._handleResponse(response);
    }
    
    // ... (All other API methods: searchWord, getWordbook, etc., remain exactly the same)
    async searchWord(query, page = 1) {
        const params = new URLSearchParams({ q: query, page: page });
        return this._request(`/api/search?${params.toString()}`, { method: 'GET' });
    }

    async getWordbook() {
        return this._request('/api/wordbook', { method: 'GET' });
    }
    
    async addToWordbook(word, definition) {
        return this._request('/api/wordbook', {
            method: 'POST',
            body: JSON.stringify({ word, definition })
        });
    }
    
    async removeFromWordbook(wordId) {
        return this._request(`/api/wordbook/${wordId}`, { method: 'DELETE' });
    }

    async generateScenario(type, options = {}) {
        const body = { level: options.level };
        if (type === 'custom' && options.situation) {
            body.situation = options.situation;
        }
        return this._request('/api/scenarios/random', {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    async transcribeAudio(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording');
        return this._request('/api/transcribe', {
            method: 'POST',
            body: formData
        });
    }

    async getAiResponse(payload) {
        return this._request('/api/get_ai_response', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }
    
    async getExampleDialogue(level, scenario) {
        return this._request('/api/example_dialogue', {
            method: 'POST',
            body: JSON.stringify({ level, situation: scenario })
        });
    }

    async getWordReport(word, wordClass, targetLanguage) {
        return this._request('/api/word-report', {
            method: 'POST',
            body: JSON.stringify({
                swedish_word: word,
                word_class: wordClass,
                target_language: targetLanguage
            })
        });
    }

    async getTranslation(text, style, targetLanguage) {
        return this._request('/api/translate', {
            method: 'POST',
            body: JSON.stringify({ text, style, target_language: targetLanguage })
        });
    }
}

export const api = new API();