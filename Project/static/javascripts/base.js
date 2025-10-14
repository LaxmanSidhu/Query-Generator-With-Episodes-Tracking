/*
  base.js
  Purpose: Code shared across all pages loaded via base.html
  - DOM ready helper
  - Small utilities
  - Theme switching (navbar)
  - Footer modal + audio
*/

// DOM ready helper: runs callback after DOM is interactive/ready
function onReady(callback) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(callback, 1);
    } else {
        document.addEventListener('DOMContentLoaded', callback);
    }
}

// Returns true if current path includes fragment
function isOn(pathFragment) {
    return window.location.pathname.includes(pathFragment);
}

// Theme switching available on all pages (navbar)
onReady(function () {
    const themeLink = document.getElementById('themeStylesheet');
    const themeSelect = document.getElementById('themeSelect');
    if (!themeLink || !themeSelect) return;

    const saved = localStorage.getItem('ui_theme') || 'pink';
    function themePath(key) {
        return '/static/themes/theme-' + key + '.css';
    }
    function applyTheme(key) {
        themeLink.setAttribute('href', themePath(key));
        localStorage.setItem('ui_theme', key);
    }

    applyTheme(saved);
    themeSelect.value = saved;
    themeSelect.addEventListener('change', function () {
        applyTheme(themeSelect.value);
    });
});

// Footer modal interactions with audio
onReady(function () {
    const meLink = document.getElementById('meLink');
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    const closeBtn = document.querySelector('#imageModal .close');
    const audio = document.getElementById('clickSound'); // <audio id="clickSound">

    if (!meLink || !modal || !modalImg || !closeBtn || !audio) return;

    // Fade-out function for audio
    function fadeOutAudio(audioEl, duration = 500) {
        const stepTime = 50;
        const steps = duration / stepTime;
        const volumeStep = audioEl.volume / steps;

        const fadeInterval = setInterval(() => {
            if (audioEl.volume > volumeStep) {
                audioEl.volume -= volumeStep;
            } else {
                audioEl.pause();
                audioEl.currentTime = 0;
                audioEl.volume = 1; // reset for next play
                clearInterval(fadeInterval);
            }
        }, stepTime);
    }

    function openModal() {
        modal.style.display = 'flex';
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        closeBtn.focus();

        // Play audio
        audio.currentTime = 0;
        audio.volume = 1;
        audio.play();
    }

    function closeModal(restoreFocus = true) {
        modal.classList.remove('open');
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');

        // Smoothly fade out audio
        fadeOutAudio(audio);

        if (restoreFocus) {
            meLink.focus();
        }
    }

    meLink.addEventListener('click', function (e) {
        e.preventDefault();
        openModal();
    });

    closeBtn.addEventListener('click', closeModal);

    window.addEventListener('click', function (e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Ensure hidden on load in case of cached inline styles (do not move focus on load)
    closeModal(false);

    // Escape key to close modal
    window.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.style.display !== 'none') {
            closeModal();
        }
    });
});
