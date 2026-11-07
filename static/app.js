let campaignPollInterval = null;
let lastFocusedTextarea = null;
let currentColumns = [];
let samplePreviewRows = [];

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFileUpload();
    initVariableTags();
    initEmailConfig();
    initWhatsAppActions();
    initCampaignControls();
    initPhoneMockupSync();

    // Check status initially
    checkWhatsAppStatus();
});

// 1. TABS NAVIGATION
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-trigger');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');
            switchTab(targetId);
        });
    });
}

function switchTab(targetId) {
    document.querySelectorAll('.tab-trigger').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const activeBtn = document.querySelector(`.tab-trigger[data-tab="${targetId}"]`);
    const activeContent = document.getElementById(targetId);

    if (activeBtn && activeContent) {
        activeBtn.classList.add('active');
        activeContent.classList.add('active');
    }
}

// 2. FILE UPLOAD & PREVIEW
function initFileUpload() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const btnLoadSample = document.getElementById('btnLoadSample');

    if (dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                uploadFile(files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
    }

    if (btnLoadSample) {
        btnLoadSample.addEventListener('click', () => {
            fetch('/api/load-sample')
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        handleParsedData(data);
                    } else {
                        alert('Error loading sample: ' + data.error);
                    }
                })
                .catch(err => alert('Network error: ' + err));
        });
    }
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const headline = document.querySelector('.drop-headline');
    const originalText = headline ? headline.innerText : 'Drag & Drop your Excel file here';
    if (headline) {
        headline.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-accent"></i> Processing ${file.name}...`;
    }

    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (headline) headline.innerText = originalText;
        if (data.success) {
            handleParsedData(data);
        } else {
            alert('Upload error: ' + (data.error || 'Failed to read spreadsheet'));
        }
    })
    .catch(err => {
        if (headline) headline.innerText = originalText;
        alert('Upload failed: ' + err);
    });
}

function handleParsedData(data) {
    currentColumns = data.columns || [];
    samplePreviewRows = data.preview || [];

    // Update Badges & Counters
    const infoBadge = document.getElementById('fileInfoBadge');
    if (infoBadge) infoBadge.classList.remove('hidden');

    const fileNameEl = document.getElementById('loadedFileName');
    if (fileNameEl) fileNameEl.innerText = data.filename;

    const rowCountEl = document.getElementById('loadedRowCount');
    if (rowCountEl) rowCountEl.innerText = `${data.total_rows} Contacts`;

    const previewBadge = document.getElementById('previewTotalBadge');
    if (previewBadge) previewBadge.innerText = `${data.total_rows} Leads Loaded`;

    const totalContactsBadge = document.getElementById('totalContactsBadge');
    if (totalContactsBadge) totalContactsBadge.innerText = data.total_rows;

    const metricTotal = document.getElementById('metricTotal');
    if (metricTotal) metricTotal.innerText = data.total_rows;

    const metricRem = document.getElementById('metricRemaining');
    if (metricRem) metricRem.innerText = data.total_rows;

    // Populate Column Selects
    populateSelect('mapPhone', currentColumns, data.detected.phone);
    populateSelect('mapEmail', currentColumns, data.detected.email);
    populateSelect('mapName', currentColumns, data.detected.name);

    // Render Preview Table
    renderTablePreview(currentColumns, data.preview);

    // Refresh Dynamic Tags in Tab 2
    renderDynamicTags(currentColumns);

    // Update Phone Mockup with First Contact Name
    if (data.preview && data.preview.length > 0 && data.detected.name) {
        const firstContact = data.preview[0];
        const firstName = firstContact[data.detected.name] || 'Ali Khan';
        const mockupName = document.getElementById('mockupContactName');
        if (mockupName) mockupName.innerText = firstName;
        updateMockupText();
    }
}

function populateSelect(selectId, columns, selectedValue) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = '<option value="">-- Do Not Send / Not Mapped --</option>';
    columns.forEach(col => {
        const opt = document.createElement('option');
        opt.value = col;
        opt.textContent = col;
        if (col === selectedValue) {
            opt.selected = true;
        }
        select.appendChild(opt);
    });
}

function renderTablePreview(columns, previewRows) {
    const table = document.getElementById('previewTable');
    if (!table || !columns || columns.length === 0) return;

    let theadHtml = '<tr><th>#</th>';
    columns.forEach(c => theadHtml += `<th>${escapeHtml(c)}</th>`);
    theadHtml += '</tr>';

    let tbodyHtml = '';
    previewRows.forEach((row, i) => {
        tbodyHtml += `<tr><td><strong>${i + 1}</strong></td>`;
        columns.forEach(col => {
            tbodyHtml += `<td>${escapeHtml(row[col] || '')}</td>`;
        });
        tbodyHtml += '</tr>';
    });

    table.innerHTML = `<thead>${theadHtml}</thead><tbody>${tbodyHtml}</tbody>`;
}

// 3. DYNAMIC VARIABLE TAGS & PHONE MOCKUP SYNC
function initVariableTags() {
    const waText = document.getElementById('waMessageText');
    const emBody = document.getElementById('emailBody');
    const emSubj = document.getElementById('emailSubject');

    [waText, emBody, emSubj].forEach(elem => {
        if (elem) {
            elem.addEventListener('focus', () => {
                lastFocusedTextarea = elem;
            });
        }
    });

    bindVariablePills();
}

function renderDynamicTags(columns) {
    const container = document.getElementById('variablesTags');
    if (!container) return;

    container.innerHTML = '';
    columns.forEach(col => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'var-tag-btn';
        btn.setAttribute('data-var', `{${col}}`);
        btn.textContent = `+ {${col}}`;
        container.appendChild(btn);
    });
    bindVariablePills();
}

function bindVariablePills() {
    document.querySelectorAll('.var-tag-btn').forEach(pill => {
        pill.onclick = () => {
            const tag = pill.getAttribute('data-var');
            insertTagAtCursor(tag);
        };
    });
}

function insertTagAtCursor(tag) {
    const target = lastFocusedTextarea || document.getElementById('waMessageText');
    if (!target) return;

    const startPos = target.selectionStart || 0;
    const endPos = target.selectionEnd || 0;
    const text = target.value;

    target.value = text.substring(0, startPos) + tag + text.substring(endPos);
    target.focus();
    target.selectionStart = target.selectionEnd = startPos + tag.length;

    updateMockupText();
}

function initPhoneMockupSync() {
    const waText = document.getElementById('waMessageText');
    if (waText) {
        waText.addEventListener('input', updateMockupText);
        updateMockupText();
    }
}

function updateMockupText() {
    const waText = document.getElementById('waMessageText');
    const mockupBubble = document.getElementById('mockupMessageText');
    if (!waText || !mockupBubble) return;

    let sampleName = 'Ali Khan';
    if (samplePreviewRows && samplePreviewRows.length > 0) {
        const nameCol = document.getElementById('mapName')?.value;
        if (nameCol && samplePreviewRows[0][nameCol]) {
            sampleName = samplePreviewRows[0][nameCol];
        }
    }

    let rendered = waText.value || '';
    rendered = rendered.replace(/{Name}/gi, sampleName);
    rendered = rendered.replace(/{Phone}/gi, '+92 300 1234567');
    rendered = rendered.replace(/{Email}/gi, 'client@example.com');
    rendered = rendered.replace(/{Company}/gi, 'Tech Solutions');

    mockupBubble.innerText = rendered || 'Type a message in the box to preview...';
}

// 4. EMAIL CONFIGURATION
function initEmailConfig() {
    const providerSelect = document.getElementById('emailProvider');
    const customFields = document.getElementById('customSmtpFields');
    const btnTest = document.getElementById('btnTestEmail');
    const testResult = document.getElementById('testEmailResult');

    if (providerSelect) {
        providerSelect.addEventListener('change', () => {
            if (providerSelect.value === 'custom') {
                customFields?.classList.remove('hidden');
            } else {
                customFields?.classList.add('hidden');
            }
        });
    }

    if (btnTest) {
        btnTest.addEventListener('click', () => {
            const email = document.getElementById('senderEmail')?.value.trim();
            const pwd = document.getElementById('senderPassword')?.value.trim();
            if (!email || !pwd) {
                alert('Please enter your Sender Email and App Password first');
                return;
            }

            testResult.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-accent"></i> Connecting to SMTP server...';

            fetch('/api/test-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider: providerSelect.value,
                    sender_email: email,
                    password: pwd,
                    custom_host: document.getElementById('customHost')?.value || '',
                    custom_port: document.getElementById('customPort')?.value || 587
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    testResult.innerHTML = `<span class="text-success"><i class="fa-solid fa-circle-check"></i> ${data.message}</span>`;
                    document.getElementById('emailStatusPill')?.classList.add('connected');
                    const textEl = document.getElementById('emailStatusText');
                    if (textEl) textEl.innerText = 'SMTP: Verified';
                } else {
                    testResult.innerHTML = `<span class="text-danger"><i class="fa-solid fa-circle-xmark"></i> ${data.message}</span>`;
                }
            })
            .catch(err => {
                testResult.innerHTML = `<span class="text-danger">Network error: ${err}</span>`;
            });
        });
    }
}

// 5. WHATSAPP ACTIONS
function initWhatsAppActions() {
    const btnLaunch = document.getElementById('btnLaunchWhatsApp');
    const btnCheck = document.getElementById('btnCheckWhatsAppStatus');
    const waDetail = document.getElementById('waDetailedStatus');

    if (btnLaunch) {
        btnLaunch.addEventListener('click', () => {
            waDetail.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-accent"></i> Opening Google Chrome for WhatsApp Web...';
            fetch('/api/whatsapp/launch', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (data.logged_in) {
                            setWhatsAppConnectedUI();
                        } else {
                            waDetail.innerHTML = '<span class="text-warning"><i class="fa-solid fa-qrcode"></i> Chrome is open! Scan the QR code in Chrome with your phone.</span>';
                            startPollingWhatsAppStatus();
                        }
                    } else {
                        waDetail.innerHTML = `<span class="text-danger">Error: ${data.error}</span>`;
                    }
                })
                .catch(err => waDetail.innerHTML = `<span class="text-danger">Launch error: ${err}</span>`);
        });
    }

    if (btnCheck) {
        btnCheck.addEventListener('click', checkWhatsAppStatus);
    }
}

function checkWhatsAppStatus() {
    fetch('/api/whatsapp/status')
        .then(res => res.json())
        .then(data => {
            if (data.logged_in) {
                setWhatsAppConnectedUI();
            } else if (data.running) {
                const waDetail = document.getElementById('waDetailedStatus');
                if (waDetail) {
                    waDetail.innerHTML = '<span class="text-warning"><i class="fa-solid fa-qrcode"></i> Chrome is open. Please scan QR code.</span>';
                }
            }
        })
        .catch(() => {});
}

function setWhatsAppConnectedUI() {
    const waDetail = document.getElementById('waDetailedStatus');
    if (waDetail) {
        waDetail.innerHTML = '<span class="text-success"><i class="fa-solid fa-circle-check"></i> WhatsApp Web is Connected & Ready!</span>';
    }
    const pill = document.getElementById('waStatusPill');
    if (pill) pill.classList.add('connected');
    const text = document.getElementById('waStatusText');
    if (text) text.innerText = 'WhatsApp: Online';
}

function startPollingWhatsAppStatus() {
    const interval = setInterval(() => {
        fetch('/api/whatsapp/status')
            .then(res => res.json())
            .then(data => {
                if (data.logged_in) {
                    clearInterval(interval);
                    setWhatsAppConnectedUI();
                }
            })
            .catch(() => {});
    }, 4000);
}

// 6. CAMPAIGN CONTROLS & REAL-TIME LOGS
function initCampaignControls() {
    const btnStart = document.getElementById('btnStartCampaign');
    const btnStop = document.getElementById('btnStopCampaign');
    const btnClearLogs = document.getElementById('btnClearLogs');

    if (btnStart) {
        btnStart.addEventListener('click', () => {
            const channels = [];
            if (document.getElementById('chkWhatsApp')?.checked) channels.push('whatsapp');
            if (document.getElementById('chkEmail')?.checked) channels.push('email');

            if (channels.length === 0) {
                alert('Please select at least one outreach channel (WhatsApp or Email)');
                return;
            }

            const phoneCol = document.getElementById('mapPhone')?.value;
            const emailCol = document.getElementById('mapEmail')?.value;
            const nameCol = document.getElementById('mapName')?.value;

            if (channels.includes('whatsapp') && !phoneCol) {
                alert('Please map the WhatsApp Phone Number column in Step 1');
                switchTab('tab-upload');
                return;
            }

            if (channels.includes('email')) {
                if (!emailCol) {
                    alert('Please map the Email column in Step 1');
                    switchTab('tab-upload');
                    return;
                }
                const senderEmail = document.getElementById('senderEmail')?.value.trim();
                const senderPassword = document.getElementById('senderPassword')?.value.trim();
                if (!senderEmail || !senderPassword) {
                    alert('Please configure your Sender Email and App Password in Step 3');
                    switchTab('tab-config');
                    return;
                }
            }

            const payload = {
                channels: channels,
                column_mapping: {
                    phone: phoneCol,
                    email: emailCol,
                    name: nameCol
                },
                whatsapp_template: document.getElementById('waMessageText')?.value || '',
                email_config: {
                    provider: document.getElementById('emailProvider')?.value || 'gmail',
                    sender_email: document.getElementById('senderEmail')?.value.trim() || '',
                    password: document.getElementById('senderPassword')?.value.trim() || '',
                    subject: document.getElementById('emailSubject')?.value || '',
                    body: document.getElementById('emailBody')?.value || '',
                    custom_host: document.getElementById('customHost')?.value || '',
                    custom_port: document.getElementById('customPort')?.value || 587,
                    is_html: false
                },
                default_country: document.getElementById('countryModeSelect')?.value || 'AUTO',
                min_delay: parseInt(document.getElementById('minDelay')?.value) || 6,
                max_delay: parseInt(document.getElementById('maxDelay')?.value) || 12
            };

            btnStart.disabled = true;
            if (btnStop) btnStop.disabled = false;

            fetch('/api/start-campaign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    switchTab('tab-campaign');
                    startProgressPolling();
                } else {
                    alert('Error starting campaign: ' + data.error);
                    btnStart.disabled = false;
                    if (btnStop) btnStop.disabled = true;
                }
            })
            .catch(err => {
                alert('Failed to start campaign: ' + err);
                btnStart.disabled = false;
                if (btnStop) btnStop.disabled = true;
            });
        });
    }

    if (btnStop) {
        btnStop.addEventListener('click', () => {
            fetch('/api/stop-campaign', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    alert(data.message);
                    btnStop.disabled = true;
                });
        });
    }

    if (btnClearLogs) {
        btnClearLogs.addEventListener('click', () => {
            const terminal = document.getElementById('terminalLogs');
            if (terminal) terminal.innerHTML = '';
        });
    }
}

function startProgressPolling() {
    if (campaignPollInterval) clearInterval(campaignPollInterval);

    campaignPollInterval = setInterval(() => {
        fetch('/api/campaign-status')
            .then(res => res.json())
            .then(state => {
                updateCampaignUI(state);
                if (!state.running && state.completed) {
                    clearInterval(campaignPollInterval);
                    const btnStart = document.getElementById('btnStartCampaign');
                    const btnStop = document.getElementById('btnStopCampaign');
                    if (btnStart) btnStart.disabled = false;
                    if (btnStop) btnStop.disabled = true;
                    if (state.has_report) {
                        const reportBtn = document.getElementById('btnDownloadReport');
                        if (reportBtn) reportBtn.style.display = 'inline-flex';
                    }
                }
            })
            .catch(() => {});
    }, 1500);
}

function updateCampaignUI(state) {
    const total = state.total || 0;
    const current = state.current_index || 0;
    const sent = state.sent_count || 0;
    const failed = state.failed_count || 0;
    const remaining = Math.max(0, total - (sent + failed));
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;

    const fill = document.getElementById('progressBarFill');
    if (fill) fill.style.width = `${percent}%`;

    const pctEl = document.getElementById('progressPercent');
    if (pctEl) pctEl.innerText = `${percent}%`;

    const targetEl = document.getElementById('currentTargetText');
    if (targetEl) {
        targetEl.innerText = state.current_name ? `Sending to: ${state.current_name} (${current}/${total})` : (state.running ? 'Starting...' : 'Completed');
    }

    const mTotal = document.getElementById('metricTotal');
    if (mTotal) mTotal.innerText = total;

    const mSent = document.getElementById('metricSent');
    if (mSent) mSent.innerText = sent;

    const mFailed = document.getElementById('metricFailed');
    if (mFailed) mFailed.innerText = failed;

    const mRemaining = document.getElementById('metricRemaining');
    if (mRemaining) mRemaining.innerText = remaining;

    // Stream logs
    if (state.logs && state.logs.length > 0) {
        const terminal = document.getElementById('terminalLogs');
        if (terminal) {
            let html = '';
            state.logs.forEach(log => {
                const levelClass = `t-msg-${log.level || 'info'}`;
                html += `<div class="t-line"><span class="t-time">[${log.time}]</span> <span class="${levelClass}">${escapeHtml(log.message)}</span></div>`;
            });
            terminal.innerHTML = html;
            terminal.scrollTop = terminal.scrollHeight;
        }
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
