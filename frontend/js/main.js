// frontend/js/main.js (FINAL CORRECTED VERSION)
import { initUI, updateNavbar, showView } from './ui.js';
import { initState } from './state.js';
import { checkAuth, initAuth } from './auth.js';
import { initConversation } from './conversation.js';
import { initTranslator } from './translator.js';
import { loadWordbook } from './wordbook.js'; 
import { state } from './state.js'; // Import state to check login status

// Import these modules so their event listeners are set up.
// These modules handle their own initialization internally.
import './search.js';

/**
 * Main Application Initialization
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("App loading...");

    // 1. Initialize global state from localStorage
    initState();

    // 2. Check for an existing auth token in localStorage
    checkAuth();

    // 3. If the user is logged in from a previous session, sync their wordbook in the background.
    if (state.isLoggedIn) {
        // We call with 'false' to prevent it from switching the view.
        loadWordbook(false);
    }

    // 4. Cache DOM elements and set up general UI event listeners
    initUI();

    // 5. Set up authentication-specific event listeners (for login/logout buttons, etc.)
    initAuth();

    // 6. Update UI components like the navbar based on the initial auth state
    updateNavbar();

    // 7. Initialize the core conversation functionality
    initConversation();
    
    // 8. Initialize the translator
    initTranslator();

    // Explicitly set the default view to 'search'
    showView('search'); 

    console.log("App initialized successfully.");
});