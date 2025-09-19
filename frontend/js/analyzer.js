// frontend/js/analyzer.js

import { API } from './api.js';
import { state } from './state.js';
import { showToast, renderAnalysisResult } from './ui.js';

const api = new API();
let analyzeBtn;
let sourceTextArea;
let resultContainer;

async function handleAnalysis() {
    if (!state.isLoggedIn) {
        showToast("Please log in to use the analyzer.");
        return;
    }

    const text = sourceTextArea.value.trim();
    if (!text) {
        showToast("Please enter some text to analyze.");
        return;
    }

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analyzing...';
    resultContainer.innerHTML = `<div class="p-2 flex-center gap-2"><span class="spinner"></span><span class="text-secondary">Generating analysis...</span></div>`;

    try {
        const response = await api.analyzeText(text, state.targetLanguage);
        renderAnalysisResult(response);
    } catch (error) {
        resultContainer.innerHTML = `<p class="text-error">Error: ${error.message}</p>`;
        showToast(error.message);
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'Analyze Text';
    }
}

export function initAnalyzer() {
    analyzeBtn = document.getElementById('analyze-btn');
    sourceTextArea = document.getElementById('text-to-analyze');
    resultContainer = document.getElementById('analysis-result');

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', handleAnalysis);
    }
}