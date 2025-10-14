/*
  home.js
  Purpose: Behaviors specific to home.html
  - Initialize DataTables for uploaded CSV
  - Handle processing progress bar
*/

onReady(function () {
    // Initialize DataTable on home page
    const tableEl = document.querySelector("#csvTableContainer table") || document.getElementById("csvTable");
    if (tableEl) {
        if (tableEl.parentElement && tableEl.parentElement.id === "csvTableContainer") {
            $(tableEl).DataTable({
                pageLength: 5,
                lengthMenu: [5, 10, 20, 50],
                autoWidth: false
            });
        } else {
            $.ajax({
                url: '/data',
                type: 'GET',
                dataType: 'json',
                success: function (json) {
                    if (!json.columns || json.columns.length === 0) return;
                    $('#csvTable').DataTable({
                        serverSide: true,
                        processing: true,
                        ajax: '/data',
                        pageLength: 5,
                        lengthMenu: [5, 10, 20, 50],
                        autoWidth: false,
                        columns: json.columns,
                        columnDefs: [{ targets: '_all', defaultContent: "" }]
                    });
                }
            });
        }
    }

    // Progress handling
    const generateBtn = document.getElementById('generateBtn');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const etaText = document.getElementById('etaText');

    if (generateBtn && progressContainer && progressBar) {
        let currentProgress = 0;
        let targetProgress = 0;
        let polling = false;

        // Smooth animation between current and target
        setInterval(function () {
            if (currentProgress < targetProgress) {
                currentProgress += (targetProgress - currentProgress) / 5;
                if (currentProgress > targetProgress) currentProgress = targetProgress;
                progressBar.style.setProperty('--progress', currentProgress + '%');
                progressBar.setAttribute('data-label', Math.round(currentProgress) + '%');
            }
        }, 50);

        function showProgressUI() {
            progressContainer.style.display = 'block';
            generateBtn.disabled = true;
        }

        function hideProgressUI() {
            progressContainer.style.display = 'none';
            generateBtn.disabled = false;
            currentProgress = 0;
            targetProgress = 0;
            progressBar.style.setProperty('--progress', '0%');
            progressBar.setAttribute('data-label', '');
            if (etaText) etaText.textContent = '';
        }

        function pollProgress() {
            if (polling) return;
            polling = true;
            (function loop() {
                $.get('/progress', function (data) {
                    // Persist for cross-page navigation
                    localStorage.setItem('proc_in_progress', data.in_progress ? '1' : '');
                    localStorage.setItem('proc_percent', String(data.percent || 0));
                    localStorage.setItem('proc_eta', data.eta || '00:00:00');

                    targetProgress = data.percent || 0;
                    if (etaText) {
                        const etaVal = (data && data.eta && data.eta !== '00:00:00') ? data.eta : 'calculating...';
                        etaText.textContent = 'Estimated time remaining: ' + etaVal;
                    }
                    if (!data.done) {
                        setTimeout(loop, 500);
                    } else {
                        targetProgress = 100;
                        localStorage.setItem('proc_in_progress', '');
                        setTimeout(function () { window.location.href = '/results'; }, 500);
                        polling = false;
                    }
                }).fail(function() {
                    // On error, stop polling but keep UI; next click can restart
                    polling = false;
                });
            })();
        }

        generateBtn.addEventListener('click', function () {
            showProgressUI();
            $.post('/process', {}, function (resp) {
                // started or already_running -> begin polling
                if (resp && resp.status === 'already_processed' && resp.redirect) {
                    window.location.href = resp.redirect;
                    return;
                }
                if (resp && (resp.status === 'started' || resp.status === 'already_running')) {
                    pollProgress();
                } else {
                    hideProgressUI();
                }
            }).fail(function() {
                hideProgressUI();
            });
        });

        // Resume progress on load only if a process is running
        $.get('/progress', function (data) {
            if (data && data.in_progress) {
                showProgressUI();
                targetProgress = data.percent || 0;
                if (etaText) {
                    const etaVal = (data && data.eta && data.eta !== '00:00:00') ? data.eta : 'calculating...';
                    etaText.textContent = 'Estimated time remaining: ' + etaVal;
                }
                pollProgress();
            } else {
                hideProgressUI();
            }
        }).fail(function() {
            // If progress endpoint fails, keep default hidden
        });
    }
});


