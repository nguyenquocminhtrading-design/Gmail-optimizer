document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadReviewQueue();
    loadTodayImportant();

    const syncBtn = document.getElementById('syncBtn');
    if (syncBtn) {
        syncBtn.addEventListener('click', runManualSync);
    }
});

async function loadDashboardStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        document.getElementById('statTotal').innerText = data.total_emails || 0;
        document.getElementById('statImportant').innerText = data.important_today || 0;
        document.getElementById('statAction').innerText = data.action_required || 0;
        document.getElementById('statUrgent').innerText = data.urgent || 0;
        document.getElementById('statReview').innerText = data.needs_review || 0;
        document.getElementById('statDeadlines').innerText = data.upcoming_deadlines || 0;
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

async function loadReviewQueue() {
    const queueContainer = document.getElementById('reviewQueueContainer');
    if (!queueContainer) return;

    try {
        const res = await fetch('/api/review');
        const emails = await res.json();

        if (emails.length === 0) {
            queueContainer.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                    🎉 No emails currently need your manual review! All emails are auto-classified.
                </div>
            `;
            return;
        }

        queueContainer.innerHTML = emails.map(email => renderReviewCard(email)).join('');
    } catch (err) {
        console.error('Error loading review queue:', err);
        queueContainer.innerHTML = `<div style="color: var(--accent-rose);">Failed to load review queue.</div>`;
    }
}

function renderReviewCard(email) {
    const cls = email.classification || {};
    const priority = cls.priority || 'NORMAL';
    const category = cls.category || 'OTHER';
    const action = cls.action_status || 'NO_ACTION';
    const reasons = JSON.parse(cls.reasons_json || '[]');

    return `
        <div class="email-card" id="email-card-${email.id}">
            <div class="email-header">
                <div>
                    <span class="email-sender">${escapeHtml(email.sender_name || email.sender_email)}</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted);">(${escapeHtml(email.sender_email)})</span>
                </div>
                <span class="email-date">${new Date(email.date_received).toLocaleString()}</span>
            </div>
            
            <div class="email-subject">${escapeHtml(email.subject)}</div>
            <div class="email-preview">${escapeHtml(email.normalized_body ? email.normalized_body.substring(0, 200) + '...' : 'No preview available')}</div>
            
            <div class="tag-list">
                <span class="tag tag-${priority.toLowerCase()}">Priority: ${priority}</span>
                <span class="tag tag-career">Category: ${category}</span>
                <span class="tag tag-action">Action: ${action}</span>
                <span class="tag" style="background: rgba(255,255,255,0.1);">Confidence: ${Math.round((cls.confidence || 0) * 100)}%</span>
            </div>

            <div class="explainability-box">
                <strong>Why predicted this way?</strong>
                <ul style="margin-top: 0.3rem; margin-left: 1.2rem;">
                    ${reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                </ul>
            </div>

            <div class="decision-actions">
                <span>Scope:</span>
                <select id="scope-${email.id}" class="scope-select">
                    <option value="THIS_EMAIL">Only this email</option>
                    <option value="THIS_SENDER">All emails from this sender</option>
                    <option value="SIMILAR_SUBJECTS">Similar subjects</option>
                </select>

                <button class="btn-accept" onclick="submitDecision(${email.id}, '${priority}', '${category}', '${action}')">
                    ✓ Accept Prediction
                </button>
                
                <button class="btn-change" onclick="showChangeModal(${email.id}, '${priority}', '${category}', '${action}')">
                    ✎ Change & Teach
                </button>
            </div>
        </div>
    `;
}

async function loadTodayImportant() {
    const container = document.getElementById('todayImportantContainer');
    if (!container) return;

    try {
        const res = await fetch('/api/important');
        const emails = await res.json();

        if (emails.length === 0) {
            container.innerHTML = `<div style="color: var(--text-muted); padding: 1rem;">No important emails recorded for today yet.</div>`;
            return;
        }

        container.innerHTML = emails.map(email => `
            <div class="email-card">
                <div class="email-header">
                    <span class="email-sender">${escapeHtml(email.sender_name || email.sender_email)}</span>
                    <span class="email-date">${new Date(email.date_received).toLocaleTimeString()}</span>
                </div>
                <div class="email-subject">${escapeHtml(email.subject)}</div>
                <div class="tag-list">
                    <span class="tag tag-${(email.classification?.priority || '').toLowerCase()}">${email.classification?.priority}</span>
                    <span class="tag tag-career">${email.classification?.category}</span>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading important emails:', err);
    }
}

async function submitDecision(emailId, priority, category, action) {
    const scopeSelect = document.getElementById(`scope-${emailId}`);
    const scope = scopeSelect ? scopeSelect.value : 'THIS_EMAIL';

    try {
        const res = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email_id: emailId,
                new_priority: priority,
                new_category: category,
                new_action: action,
                scope: scope
            })
        });

        if (res.ok) {
            const card = document.getElementById(`email-card-${emailId}`);
            if (card) {
                card.style.opacity = '0.5';
                card.style.pointerEvents = 'none';
                setTimeout(() => card.remove(), 400);
            }
            loadDashboardStats();
        } else {
            alert('Failed to submit decision.');
        }
    } catch (err) {
        console.error('Error submitting decision:', err);
    }
}

function showChangeModal(emailId, currentPriority, currentCategory, currentAction) {
    const newPriority = prompt('Select Priority (URGENT, IMPORTANT, NORMAL, LOW_PRIORITY):', currentPriority);
    if (!newPriority) return;

    const newCategory = prompt('Select Category (CAREER, UNIVERSITY, FINANCE, WORK, PERSONAL, NEWSLETTER, PROMOTION, OTHER):', currentCategory);
    if (!newCategory) return;

    const newAction = prompt('Select Action (ACTION_REQUIRED, WAITING_FOR_REPLY, NO_ACTION, FOLLOW_UP):', currentAction);
    if (!newAction) return;

    submitDecision(emailId, newPriority.toUpperCase(), newCategory.toUpperCase(), newAction.toUpperCase());
}

async function runManualSync() {
    const syncBtn = document.getElementById('syncBtn');
    syncBtn.innerText = 'Syncing... ⏳';
    syncBtn.disabled = true;

    try {
        const res = await fetch('/api/sync', { method: 'POST' });
        const data = await res.json();
        alert(`Sync completed! Processed ${data.processed_count || 0} emails.`);
        loadDashboardStats();
        loadReviewQueue();
        loadTodayImportant();
    } catch (err) {
        alert('Sync error or credentials not authenticated yet.');
    } finally {
        syncBtn.innerText = 'Sync Gmail Now 🔄';
        syncBtn.disabled = false;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
