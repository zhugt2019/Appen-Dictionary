// frontend/js/state.js

// A simple, shared state object for a portion of the application.
export const state = {
    // Auth state
    isLoggedIn: false,
    authToken: null,
    refreshToken: null, // ADDED: To store the long-lived refresh token
    username: null,

    // Conversation-specific state
    currentLevel: 'A2',
    currentScenario: '',
    messages: [],
    isRecording: false,
    isLoading: false,

    wordbookWords: new Set(), // Use a Set for efficient lookups.

    // Target language for dynamic translations. Default to Chinese.
    targetLanguage: 'zh',
};

// Initializes state from localStorage.
export function initState() {
    // This part is for non-auth state, which is fine
    const level = localStorage.getItem('appen_level');
    if (level) {
        state.currentLevel = level;
    }
    
    const savedLang = localStorage.getItem('targetLanguage');
    if (savedLang) {
        state.targetLanguage = savedLang;
    }

    // MODIFIED: Although checkAuth in auth.js handles the main auth check,
    // we can pre-populate the state here for consistency.
    state.authToken = localStorage.getItem('authToken');
    state.refreshToken = localStorage.getItem('refreshToken');
    state.username = localStorage.getItem('username');
    state.isLoggedIn = !!(state.authToken && state.refreshToken && state.username);


    console.log("Initial state loaded:", state);
}

// MODIFIED: Function to update the auth state with both tokens
export function setAuthState(isLoggedIn, authToken, refreshToken, username) {
    state.isLoggedIn = isLoggedIn;
    state.authToken = authToken;
    state.refreshToken = refreshToken; // MODIFIED: Handle the refresh token
    state.username = username;

    if (isLoggedIn && authToken && refreshToken) {
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('refreshToken', refreshToken); // MODIFIED: Store the refresh token
        localStorage.setItem('username', username);
    } else {
        // Clear all auth-related items on logout
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken'); // MODIFIED: Remove the refresh token
        localStorage.removeItem('username');
        state.wordbookWords.clear(); // Clear the wordbook cache on logout.
    }
    console.log("Auth state updated:", state);
}