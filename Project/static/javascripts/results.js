// results-final.js
(function () {
    // DOM ready
    function onReady(cb) {
        if (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(cb, 1);
        else document.addEventListener('DOMContentLoaded', cb);
    }

    // small helpers
    function safeText(node) { return node ? (node.innerText || node.textContent || '').trim() : ''; }
    function q(container, sel) { return (container || document).querySelector(sel); }
    function qa(container, sel) { return Array.from((container || document).querySelectorAll(sel)); }

    function addDisabledSectionTo(container) {
        if (!container) return;
        const s = q(container, '.suggestions');
        const p = q(container, '#keyword_planner_section_wrapper');
        const pb = q(container, '#showPlannerBtn');
        if (s) s.classList.add('disabled-section');
        if (p) p.classList.add('disabled-section');
        if (pb) pb.classList.add('disabled-section');
    }

    function removeDisabledSectionFrom(container) {
        if (!container) return;
        const s = q(container, '.suggestions');
        const p = q(container, '#keyword_planner_section_wrapper');
        const pb = q(container, '#showPlannerBtn');
        if (s) s.classList.remove('disabled-section');
        if (p) p.classList.remove('disabled-section');
        if (pb) pb.classList.remove('disabled-section');
    }

    // TABS: initialize suggestions tabs (no delegation here)
    function initializeSuggestions(container) {
        if (!container) return;
        const suggestions = q(container, '.suggestions');
        if (!suggestions) return;
        const buttons = qa(suggestions, '.buttons .btn');
        const groups = ['one_word', 'two_word', 'one_word_podcasts', 'two_word_podcasts'];

        // remove previous listeners by replacing nodes
        buttons.forEach(b => b.parentNode && b.parentNode.replaceChild(b.cloneNode(true), b));
        const newButtons = qa(suggestions, '.buttons .btn');

        newButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const targetId = btn.getAttribute('data-target');
                groups.forEach(id => {
                    const el = q(suggestions, `#${id}`);
                    if (!el) return;
                    el.classList.toggle('hidden', id !== targetId);
                });
                newButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        if (newButtons.length && !newButtons.some(b => b.classList.contains('active'))) newButtons[0].click();
    }

    // Keyword planner: only set initial text here; actual toggle handled by delegation to avoid duplicate/cloned-button mismatch
    function initializeKeywordPlanner(container) {
        if (!container) return;
        const plannerWrapper = q(container, '#keyword_planner_section_wrapper');
        const plannerBtn = q(container, '#showPlannerBtn');
        if (!plannerWrapper || !plannerBtn) return;
        plannerBtn.textContent = plannerWrapper.classList.contains('hidden') ? 'Click for Keyword Planner' : 'Hide Keyword Planner';
    }

    // Copy buttons (re-init after injection)
    function initializeCopyButtons(container) {
        if (!container) return;
        const copyBtns = qa(container, '.planner-card .copy-btn');
        copyBtns.forEach(b => b.parentNode && b.parentNode.replaceChild(b.cloneNode(true), b));
        qa(container, '.planner-card .copy-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const targetId = btn.getAttribute('data-copy-target');
                const target = document.getElementById(targetId) || q(container, `#${targetId}`);
                if (!target) return;
                const text = target.innerText || target.textContent || '';
                navigator.clipboard.writeText(text).then(() => {
                    const original = btn.textContent;
                    btn.textContent = '✓';
                    setTimeout(() => btn.textContent = original, 900);
                    let toast = document.querySelector('.copy-toast');
                    if (!toast) { toast = document.createElement('div'); toast.className = 'copy-toast'; document.body.appendChild(toast); }
                    toast.textContent = 'Copied!';
                    toast.classList.add('show');
                    clearTimeout(window.__copyToastTimer);
                    window.__copyToastTimer = setTimeout(() => toast.classList.remove('show'), 1200);
                }).catch(err => console.error('clipboard failed', err));
            });
        });
    }

    // Episode controls: prepare refresh function; it updates UI based on server response
    function setupEpisodeControls(container) {
        if (!container) return;

        function setStatusElems(statusEl, markBtn, analyzed) {
            if (!statusEl) return;
            statusEl.textContent = analyzed ? '✅ Analyzed' : '❌ Not Yet Analyzed';
            statusEl.dataset.analyzed = analyzed ? 'true' : 'false';
            if (markBtn) markBtn.textContent = analyzed ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
        }

        async function refreshEpisodeStatus(title) {
            if (!title) return;
            try {
                const res = await fetch(`/get_episode_status?title=${encodeURIComponent(title)}`);
                if (!res.ok) return;
                const data = await res.json();
                const statusText = document.getElementById('episodeStatusText') || q(container, '#episodeStatusText');
                const markBtn = document.getElementById('markEpisodeBtn') || q(container, '#markEpisodeBtn');
                setStatusElems(statusText, markBtn, !!(data.Analyzed !== undefined ? data.Analyzed : data.analyzed));
                const queryCounterEl = document.getElementById('queryCounter') || q(container, '#queryCounter');
                const savedQueriesText = document.getElementById('savedQueriesText') || q(container, '#savedQueriesText');
                if (queryCounterEl) queryCounterEl.textContent = data.saved_count || 0;
                if (savedQueriesText) savedQueriesText.textContent = (data.saved_queries || []).join(', ');
                // reflect saved queries on cards
                const allCards = qa(container, '.cards .card');
                const savedSet = new Set((data.saved_queries || []).map(s => s.toLowerCase()));
                allCards.forEach(card => {
                    const textNode = safeText(card).replace('➕', '').replace('−', '').trim();
                    let btn = card.querySelector('.add-query-btn, .remove-query-btn');
                    if (!btn) {
                        btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'add-query-btn';
                        btn.title = 'Add to saved queries';
                        btn.textContent = '➕';
                        card.appendChild(btn);
                    }
                    if (savedSet.has(textNode.toLowerCase())) {
                        btn.textContent = '−';
                        btn.classList.add('remove-query-btn'); btn.classList.remove('add-query-btn'); btn.title = 'Remove from saved queries';
                    } else {
                        btn.textContent = '➕';
                        btn.classList.add('add-query-btn'); btn.classList.remove('remove-query-btn'); btn.title = 'Add to saved queries';
                    }
                });
            } catch (err) {
                console.error('refreshEpisodeStatus', err);
            }
        }

        container._refreshEpisodeStatus = refreshEpisodeStatus;
    }

    function updateAnalyzedSummary(newAnalyzedFlag, prevAnalyzedFlag) {
        try {
            const summary = document.querySelector('.analyzed-summary');
            if (!summary || newAnalyzedFlag === prevAnalyzedFlag) return;
            const analyzedEl = summary.querySelector('.count strong');
            const totalEl = summary.querySelector('.count .total');
            const pctLabel = summary.querySelector('.progressbar .pct-label');
            const bar = summary.querySelector('.progressbar .bar');
            const hint = summary.querySelector('.hint');

            const current = Math.max(0, parseInt((analyzedEl && analyzedEl.textContent) || '0', 10) || 0);
            const total = Math.max(0, parseInt((totalEl && totalEl.textContent) || '0', 10) || 0);
            const delta = newAnalyzedFlag ? 1 : -1;
            const next = Math.min(total, Math.max(0, current + delta));
            if (analyzedEl) analyzedEl.textContent = String(next);
            const pct = total > 0 ? Math.floor((next * 100) / total) : 0;
            if (pctLabel) pctLabel.textContent = `${pct}%`;
            if (bar) bar.style.width = `${pct}%`;
            if (hint) hint.style.display = next === 0 ? '' : 'none';
        } catch (e) {
            console.warn('updateAnalyzedSummary failed', e);
        }
    }

    // Ensure the mark button is wired directly to the live DOM node
    function wireMarkButton(container) {
        if (!container) return;
        // find latest button (look globally too in case it's rendered outside)
        const btn = document.getElementById('markEpisodeBtn') || container.querySelector('#markEpisodeBtn');
        if (!btn) return;

        // replace node to remove duplicate listeners, then attach
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);

        newBtn.addEventListener('click', async function (ev) {
            ev.preventDefault(); // prevent form submit if it's inside a form
            try {
                const dropdown = document.querySelector("select[name='title']");
                if (!dropdown) {
                    console.error('mark button: dropdown not found');
                    return;
                }
                const title = dropdown.value;
                const statusText = document.getElementById('episodeStatusText') || container.querySelector('#episodeStatusText');

                const currentAnalyzed = statusText && statusText.dataset && statusText.dataset.analyzed === 'true';
                // optimistic UI
                if (statusText) {
                    statusText.textContent = currentAnalyzed ? '❌ Not Yet Analyzed' : '✅ Analyzed';
                    statusText.dataset.analyzed = (!currentAnalyzed).toString();
                }
                newBtn.textContent = currentAnalyzed ? 'Mark Episode Analyzed' : 'Unmark Episode Analyzed';

                const res = await fetch('/mark_episode_analyzed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: title, value: !currentAnalyzed })
                });

                if (!res.ok) {
                    throw new Error('Network response not OK: ' + res.status);
                }
                const data = await res.json();
                if (data && data.success !== false) {
                    const analyzedFlag = (data.Analyzed !== undefined ? data.Analyzed : data.analyzed);
                    if (statusText) {
                        statusText.textContent = analyzedFlag ? '✅ Analyzed' : '❌ Not Yet Analyzed';
                        statusText.dataset.analyzed = analyzedFlag ? 'true' : 'false';
                    }
                    newBtn.textContent = analyzedFlag ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
                    updateAnalyzedSummary(!!analyzedFlag, !!currentAnalyzed);
                } else {
                    // revert
                    if (statusText) statusText.textContent = currentAnalyzed ? '✅ Analyzed' : '❌ Not Yet Analyzed';
                    newBtn.textContent = currentAnalyzed ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
                    console.error('mark button: server returned failure', data);
                }
            } catch (err) {
                console.error('mark button error', err);
                // Attempt to revert optimistic UI
                const statusText = document.getElementById('episodeStatusText') || container.querySelector('#episodeStatusText');
                if (statusText) {
                    const prev = statusText.dataset && statusText.dataset.analyzed === 'true';
                    statusText.textContent = prev ? '✅ Analyzed' : '❌ Not Yet Analyzed';
                }
                // Show quick alert so you notice the failure during debugging
                alert('Error marking episode analyzed. See console for details.');
            }
        });
    }

    // Analysis Status Modal Functions
    function showAnalysisStatusModal() {
        const modal = document.getElementById('analysisStatusModal');
        if (!modal) {
            console.error('Analysis modal not found');
            return;
        }

        // Show modal with loading state
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        // Fetch analysis status data
        fetch('/get_analysis_status')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error fetching analysis status:', data.error);
                    // Show a helpful message instead of hiding modal
                    populateAnalysisModal({
                        analyzed_episodes: [],
                        not_analyzed_episodes: [],
                        total_episodes: 0,
                        analyzed_count: 0,
                        not_analyzed_count: 0,
                        error: data.error
                    });
                    return;
                }
                populateAnalysisModal(data);
            })
            .catch(error => {
                console.error('Error fetching analysis status:', error);
                // Show error in modal instead of hiding it
                populateAnalysisModal({
                    analyzed_episodes: [],
                    not_analyzed_episodes: [],
                    total_episodes: 0,
                    analyzed_count: 0,
                    not_analyzed_count: 0,
                    error: 'Unable to fetch analysis data. Please ensure you have uploaded a CSV file.'
                });
            });
    }

    function hideAnalysisStatusModal() {
        const modal = document.getElementById('analysisStatusModal');
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    function populateAnalysisModal(data) {
        // Update summary counts
        const totalCountEl = document.getElementById('totalEpisodesCount');
        const analyzedCountEl = document.getElementById('analyzedCount');
        const notAnalyzedCountEl = document.getElementById('notAnalyzedCount');

        if (totalCountEl) totalCountEl.textContent = data.total_episodes || 0;
        if (analyzedCountEl) analyzedCountEl.textContent = data.analyzed_count || 0;
        if (notAnalyzedCountEl) notAnalyzedCountEl.textContent = data.not_analyzed_count || 0;

        // Check if there's an error
        if (data.error) {
            const analyzedListEl = document.getElementById('analyzedEpisodesList');
            const notAnalyzedListEl = document.getElementById('notAnalyzedEpisodesList');
            
            if (analyzedListEl) {
                analyzedListEl.innerHTML = `<div class="empty-state">${data.error}</div>`;
            }
            if (notAnalyzedListEl) {
                notAnalyzedListEl.innerHTML = '<div class="empty-state">No data available</div>';
            }
            return;
        }

        // Populate analyzed episodes
        const analyzedListEl = document.getElementById('analyzedEpisodesList');
        if (analyzedListEl) {
            if (data.analyzed_episodes && data.analyzed_episodes.length > 0) {
                analyzedListEl.innerHTML = data.analyzed_episodes
                    .map(episode => `<span class="episode-item analyzed-episode">${episode}</span>`)
                    .join('');
            } else {
                analyzedListEl.innerHTML = '<div class="empty-state">No episodes analyzed yet</div>';
            }
        }

        // Populate not analyzed episodes
        const notAnalyzedListEl = document.getElementById('notAnalyzedEpisodesList');
        if (notAnalyzedListEl) {
            if (data.not_analyzed_episodes && data.not_analyzed_episodes.length > 0) {
                notAnalyzedListEl.innerHTML = data.not_analyzed_episodes
                    .map(episode => `<span class="episode-item not-analyzed-episode">${episode}</span>`)
                    .join('');
            } else {
                notAnalyzedListEl.innerHTML = '<div class="empty-state">All episodes have been analyzed</div>';
            }
        }
    }

    // Single delegated click handler on stable container
    function wireContainerDelegation(container) {
        if (!container) return;
        container.addEventListener('click', async function (e) {
            const target = e.target;



            // 1) Mark/Unmark episode (use closest)
            const markBtnMatch = target.closest && target.closest('#markEpisodeBtn');
            if (markBtnMatch) {
                e.preventDefault();
                const dropdown = document.querySelector("select[name='title']");
                if (!dropdown) return;
                const title = dropdown.value;
                const statusText = document.getElementById('episodeStatusText') || q(container, '#episodeStatusText');
                const markBtn = document.getElementById('markEpisodeBtn') || q(container, '#markEpisodeBtn');
                if (!markBtn) return;
                const currentAnalyzed = statusText && statusText.dataset && statusText.dataset.analyzed === 'true';
                // optimistic UI
                if (statusText) { statusText.textContent = currentAnalyzed ? '❌ Not Yet Analyzed' : '✅ Analyzed'; statusText.dataset.analyzed = (!currentAnalyzed).toString(); }
                if (markBtn) markBtn.textContent = currentAnalyzed ? 'Mark Episode Analyzed' : 'Unmark Episode Analyzed';
                try {
                    const res = await fetch('/mark_episode_analyzed', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: title, value: !currentAnalyzed })
                    });
                    const data = await res.json();
                    if (data && data.success !== false) {
                        const analyzedFlag = (data.Analyzed !== undefined ? data.Analyzed : data.analyzed);
                        if (statusText) { statusText.textContent = analyzedFlag ? '✅ Analyzed' : '❌ Not Yet Analyzed'; statusText.dataset.analyzed = analyzedFlag ? 'true' : 'false'; }
                        if (markBtn) markBtn.textContent = analyzedFlag ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
                    } else {
                        // revert
                        if (statusText) statusText.textContent = currentAnalyzed ? '✅ Analyzed' : '❌ Not Yet Analyzed';
                        if (markBtn) markBtn.textContent = currentAnalyzed ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
                    }
                } catch (err) {
                    console.error(err);
                    if (statusText) statusText.textContent = currentAnalyzed ? '✅ Analyzed' : '❌ Not Yet Analyzed';
                    if (markBtn) markBtn.textContent = currentAnalyzed ? 'Unmark Episode Analyzed' : 'Mark Episode Analyzed';
                    alert('Error marking episode analyzed');
                }
                return;
            }

            // 2) Planner toggle (delegated) — uses live DOM nodes and toggles text
            const plannerBtnMatch = target.closest && target.closest('#showPlannerBtn');
            if (plannerBtnMatch) {
                e.preventDefault();
                const plannerWrapper = document.getElementById('keyword_planner_section_wrapper') || q(container, '#keyword_planner_section_wrapper');
                const plannerBtn = document.getElementById('showPlannerBtn') || q(container, '#showPlannerBtn');
                if (!plannerWrapper || !plannerBtn) return;
                plannerWrapper.classList.toggle('hidden');
                plannerBtn.textContent = plannerWrapper.classList.contains('hidden') ? 'Click for Keyword Planner' : 'Hide Keyword Planner';
                return;
            }

            // 3) Add query (plus)
            if (target.classList && target.classList.contains('add-query-btn')) {
                e.preventDefault();
                const btn = target;
                const card = btn.closest('.card');
                if (!card) return;
                const word = safeText(card).replace('➕', '').replace('−', '').trim();
                const dropdown = document.querySelector("select[name='title']");
                if (!dropdown) return;
                const title = dropdown.value;
                btn.disabled = true;
                const prevText = btn.textContent, prevTitle = btn.title;
                btn.textContent = '−'; btn.classList.remove('add-query-btn'); btn.classList.add('remove-query-btn'); btn.title = 'Remove from saved queries';
                try {
                    const res = await fetch('/add_query', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: title, query: word })
                    });
                    const data = await res.json();
                    if (data && data.success !== false) {
                        const queryCounterEl = document.getElementById('queryCounter') || q(container, '#queryCounter');
                        const savedQueriesText = document.getElementById('savedQueriesText') || q(container, '#savedQueriesText');
                        if (queryCounterEl) queryCounterEl.textContent = data.saved_count || queryCounterEl.textContent;
                        if (savedQueriesText) savedQueriesText.textContent = (data.saved_queries || []).join(', ');
                        btn.disabled = false;
                        return;
                    }
                    // revert on failure
                    btn.textContent = prevText; btn.classList.add('add-query-btn'); btn.classList.remove('remove-query-btn'); btn.title = prevTitle;
                } catch (err) {
                    console.error(err);
                    btn.textContent = prevText; btn.classList.add('add-query-btn'); btn.classList.remove('remove-query-btn'); btn.title = prevTitle;
                } finally { btn.disabled = false; }
                return;
            }

            // 4) Remove query (minus)
            if (target.classList && target.classList.contains('remove-query-btn')) {
                e.preventDefault();
                const btn = target;
                const card = btn.closest('.card');
                if (!card) return;
                const word = safeText(card).replace('➕', '').replace('−', '').trim();
                const dropdown = document.querySelector("select[name='title']");
                if (!dropdown) return;
                const title = dropdown.value;
                btn.disabled = true;
                const prevText = btn.textContent, prevTitle = btn.title;
                btn.textContent = '➕'; btn.classList.remove('remove-query-btn'); btn.classList.add('add-query-btn'); btn.title = 'Add to saved queries';
                try {
                    const res = await fetch('/remove_query', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: title, query: word })
                    });
                    const data = await res.json();
                    if (data && data.success !== false) {
                        const queryCounterEl = document.getElementById('queryCounter') || q(container, '#queryCounter');
                        const savedQueriesText = document.getElementById('savedQueriesText') || q(container, '#savedQueriesText');
                        if (queryCounterEl) queryCounterEl.textContent = data.saved_count || queryCounterEl.textContent;
                        if (savedQueriesText) savedQueriesText.textContent = (data.saved_queries || []).join(', ');
                        btn.disabled = false;
                        return;
                    }
                    // revert on failure
                    btn.textContent = prevText; btn.classList.add('remove-query-btn'); btn.classList.remove('add-query-btn'); btn.title = prevTitle;
                } catch (err) {
                    console.error(err);
                    btn.textContent = prevText; btn.classList.add('remove-query-btn'); btn.classList.remove('add-query-btn'); btn.title = prevTitle;
                } finally { btn.disabled = false; }
                return;
            }
        });
    }

    // Main initialization and wiring
    onReady(function () {
        // Add direct event listener for the pill (always available, outside combinedContainer)
        const episodesPill = document.getElementById('episodesAnalyzedPill');
        if (episodesPill) {
            episodesPill.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showAnalysisStatusModal();
            });
        }

        // Add specific event listeners for analysis modal (always available)
        const analysisModal = document.getElementById('analysisStatusModal');
        const closeAnalysisBtn = document.getElementById('closeAnalysisModal');
        
        if (closeAnalysisBtn) {
            closeAnalysisBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                hideAnalysisStatusModal();
            });
        }

        if (analysisModal) {
            // Close modal when clicking on overlay (but not on modal content)
            analysisModal.addEventListener('click', function(e) {
                if (e.target === analysisModal) {
                    e.preventDefault();
                    e.stopPropagation();
                    hideAnalysisStatusModal();
                }
            });

            // ESC key handler specifically for analysis modal
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape' && analysisModal.classList.contains('show')) {
                    // Only close analysis modal if it's open and footer modal is not open
                    const footerModal = document.getElementById('imageModal');
                    if (!footerModal || footerModal.style.display === 'none') {
                        e.preventDefault();
                        e.stopPropagation();
                        hideAnalysisStatusModal();
                    }
                }
            });
        }

        const container = document.getElementById('combinedContainer');
        const dropdown = document.querySelector("select[name='title']");
        const getSuggestionsBtn = document.querySelector("button[type='submit']");

        if (!container) {
            return;
        }

        // wire delegated handler once on stable container
        wireContainerDelegation(container);

        // initialize any server-rendered content
        initializeSuggestions(container);
        initializeKeywordPlanner(container);
        initializeCopyButtons(container);
        setupEpisodeControls(container);
        wireMarkButton(container);

        // initial episode-status refresh if available
        if (container._refreshEpisodeStatus && dropdown && dropdown.value) container._refreshEpisodeStatus(dropdown.value);

        // dropdown change: blur heavy sections and refresh episode-controls
        if (dropdown) {
            dropdown.addEventListener('change', function () {
                addDisabledSectionTo(container);
                if (container._refreshEpisodeStatus) container._refreshEpisodeStatus(dropdown.value);
            });
        }

        // Get Suggestions button: fetch partial and re-init
        if (getSuggestionsBtn) {
            getSuggestionsBtn.addEventListener('click', async function (ev) {
                ev.preventDefault();
                addDisabledSectionTo(container);
                try {
                    const fd = new FormData();
                    fd.append('title', dropdown ? dropdown.value : '');
                    const res = await fetch('/get_suggestions', { method: 'POST', body: fd });
                    const data = await res.json();
                    if (!data || data.success === false) {
                        alert('⚠ ' + (data && data.error ? data.error : 'Unknown error fetching suggestions'));
                        return;
                    }
                    // inject partial (partial MUST NOT include outer #combinedContainer wrapper)
                    container.innerHTML = data.html;
                    // re-init on newly inserted DOM
                    initializeSuggestions(container);
                    initializeKeywordPlanner(container);
                    initializeCopyButtons(container);
                    setupEpisodeControls(container);
                    wireMarkButton(container);
                    removeDisabledSectionFrom(container);
                    // refresh episode status after re-init
                    if (container._refreshEpisodeStatus && dropdown && dropdown.value) {
                        setTimeout(() => container._refreshEpisodeStatus(dropdown.value), 50);
                    }
                } catch (err) {
                    console.error(err);
                    alert('Error fetching suggestions');
                }
            });
        }
    });
})();