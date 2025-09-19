//
import { api } from './api.js';
import { state } from './state.js';
import { showToast } from './ui.js';

let translateBtn;
let sourceTextArea;
let resultContainer;
let loadingIndicator; 
let historyContainer;

const HISTORY_KEY = 'translationHistory';

function renderTranslationHistory() {
    if (!historyContainer) return;
    historyContainer.innerHTML = '';
    const history = JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    if (history.length === 0) {
        historyContainer.innerHTML = `<p class="text-secondary text-center">No history yet.</p>`;
        return;
    }
    history.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'history-item';
        itemDiv.innerHTML = `
            <div class="source-text">${item.source}</div>
            <div class="translation-text">${item.translation.replace(/\n/g, '<br>')}</div>
        `;
        // Add click listener to re-populate the textarea and result
        itemDiv.addEventListener('click', () => {
            sourceTextArea.value = item.source;
            resultContainer.innerHTML = item.translation.replace(/\n/g, '<br>');
        });
        historyContainer.appendChild(itemDiv);
    });
}

// --- ADD THIS NEW FUNCTION ---
function saveTranslationToHistory(source, translation) {
    let history = JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    const newEntry = { source, translation, timestamp: new Date().getTime() };
    // Add new entry to the beginning
    history.unshift(newEntry);
    // Keep only the latest 10 entries
    if (history.length > 10) {
        history = history.slice(0, 10);
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

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
        saveTranslationToHistory(text, response.translation);
        renderTranslationHistory();
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
    loadingIndicator = document.getElementById('translator-loading-indicator');
    historyContainer = document.getElementById('translation-history');

    if (translateBtn) {
        translateBtn.addEventListener('click', handleTranslation);
    }
    // Render history on initial load
    renderTranslationHistory();
}