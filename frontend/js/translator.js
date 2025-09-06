//
import { api } from './api.js';
import { state } from './state.js';
import { showToast } from './ui.js';

let translateBtn;
let sourceTextArea;
let resultContainer;
// --- ADD THIS ---
let loadingIndicator; 

async function handleTranslation() {
    if (!state.isLoggedIn) {
        showToast("Please log in to use the translator.");
        return;
    }

    const text = sourceTextArea.value.trim();
    if (!text) {
        showToast("Please enter some text to translate.");
        return;
    }

    const style = document.querySelector('input[name="translation-style"]:checked').value;
    
    translateBtn.disabled = true;
    translateBtn.classList.add('active'); // Add .active class to signify loading state
    
    loadingIndicator.style.display = 'flex';
    loadingIndicator.innerHTML = `<span class="spinner"></span> Generating results...`;
    
    resultContainer.innerHTML = '';

    try {
        const response = await api.getTranslation(text, style, state.targetLanguage);
        resultContainer.innerHTML = response.translation.replace(/\n/g, '<br>');
    } catch (error) {
        resultContainer.textContent = `Error: ${error.message}`;
        showToast(error.message);
    } finally {
        // --- MODIFY START: New cleanup logic ---
        translateBtn.disabled = false; // Re-enable the button
        // We NO LONGER need to change the button text back.

        // Hide the loading indicator
        loadingIndicator.style.display = 'none';
        // --- MODIFY END ---
    }
}

export function initTranslator() {
    translateBtn = document.getElementById('translate-btn');
    sourceTextArea = document.getElementById('text-to-translate');
    resultContainer = document.getElementById('translation-result');
    // --- ADD THIS ---
    loadingIndicator = document.getElementById('translator-loading-indicator');

    if (translateBtn) {
        translateBtn.addEventListener('click', handleTranslation);
    }
}