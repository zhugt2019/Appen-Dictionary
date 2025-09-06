// frontend/js/translator.js

import { api } from './api.js';
import { state } from './state.js';
import { showToast } from './ui.js';

let translateBtn;
let sourceTextArea;
let resultContainer;

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
    translateBtn.textContent = 'Translating...';
    resultContainer.textContent = '';

    try {
        // Pass the targetLanguage from the global state
        const response = await api.getTranslation(text, style, state.targetLanguage);
        resultContainer.innerHTML = response.translation.replace(/\n/g, '<br>');
    } catch (error) {
        resultContainer.textContent = `Error: ${error.message}`;
        showToast(error.message);
    } finally {
        translateBtn.disabled = false;
        translateBtn.textContent = 'Translate';
    }
}

export function initTranslator() {
    translateBtn = document.getElementById('translate-btn');
    sourceTextArea = document.getElementById('text-to-translate');
    resultContainer = document.getElementById('translation-result');

    if (translateBtn) {
        translateBtn.addEventListener('click', handleTranslation);
    }
}