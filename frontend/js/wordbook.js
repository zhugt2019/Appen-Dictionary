// frontend/js/wordbook.js (FINAL and CORRECTED)
import { state } from './state.js';
import { API } from './api.js';
import { renderWordbookList, showToast, showView } from './ui.js';

const api = new API();

// This function is now EXPORTED so ui.js can call it.
export async function loadWordbook() {
    showView('wordbook'); 
    renderWordbookList(null);
    try {
        if (!state.isLoggedIn) {
            renderWordbookList([]);
            return;
        }
        const entries = await api.getWordbook();
        // Clear the set and repopulate it with the latest data from the API.
        state.wordbookWords.clear();
        entries.forEach(entry => state.wordbookWords.add(entry.word));
        renderWordbookList(entries);
    } catch (error) {
        console.error("Failed to load wordbook:", error);
        showToast(error.message);
        renderWordbookList([]);
    }
}

async function handleGlobalClickActions(event) {
    const target = event.target;
    if (target.matches('.btn-add-wordbook')) {
        if (!state.isLoggedIn) {
            showToast("Please log in to add words to your wordbook.");
            return;
        }
        target.disabled = true;
        target.textContent = 'Adding...';
        const word = target.dataset.word;
        const definition = target.dataset.definition;
        try {
            await api.addToWordbook(word, definition);
            state.wordbookWords.add(word); // Update the state cache.
            showToast(`'${word}' added to your wordbook.`);
            target.textContent = 'Added';
        } catch (error) {
            showToast(error.message);
            target.disabled = false;
            target.textContent = 'Add';
        }
    }
    if (target.matches('.btn-remove-wordbook')) {
        target.disabled = true;
        const wordId = target.dataset.id;
        const itemElement = target.closest('.wordbook-item');

        // FIX: Get the word text from the element BEFORE the API call.
        const word = itemElement.querySelector('h4').textContent;

        try {
            await api.removeFromWordbook(wordId);

            // --- Correct Order: First update state, then update UI ---
            state.wordbookWords.delete(word); // 1. Update the state cache.
            itemElement.remove();             // 2. Remove the element from the DOM.

            showToast('Word removed.');
        } catch (error) {
            showToast(error.message);
            target.disabled = false;
        }
    }
}

// The setup function is removed, and we now use a single delegated listener.
document.body.addEventListener('click', handleGlobalClickActions);