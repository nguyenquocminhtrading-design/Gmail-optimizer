/* ============================================================
   Gmail Optimizer — Dashboard JS
   Handles: tab switching, stats, review queue, inbox,
            toast notifications, Change & Teach modal
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadReviewQueue();
    loadTodayImportant();
    loadInboxTab();

    // Sync button
    const syncBtn = document.getElementById('syncBtn');
    if (syncBtn) syncBtn.addEventListener('click', runManualSync);

    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Inbox filter buttons
    document.querySelectorAll('.inbox-filter-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.inbox-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterInbox(btn.dataset.filter);
        });
    });

    // Modal overlay click to close
    const modalOverlay = document.getElementById('changeModal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeChangeModal();
        });
    }

    // Keyboard: Escape closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeChangeModal();
    });

    // Auto Background Sync every 90 seconds
    setInterval(() => {
        fetch('/api/sync', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.processed_count > 0) {
                    loadDashboardStats();
                    loadReviewQueue();
                    loadTodayImportant();
                    loadInboxTab();
                }
            })
            .catch(err => console.debug('Background sync skipped:', err));
    }, 90000);
});

/* ─────────────────────────────────────────────────────────────
   TAB SWITCHING — smooth opacity + translate transition
───────────────────────────────────────────────────────────── */
let _currentTab = 'chat';

function switchTab(tabId) {
    if (tabId === _currentTab) return;
    _currentTab = tabId;

    document.querySelectorAll('.tab-btn').forEach((btn) => {
        const isActive = btn.dataset.tab === tabId;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    document.querySelectorAll('.tab-panel').forEach((panel) => {
        if (panel.id === `tab-${tabId}`) {
            panel.style.display = 'flex';
            // Force reflow for animation
            panel.getBoundingClientRect();
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
            // Hide after transition ends
            panel.addEventListener('transitionend', function hide() {
                if (!panel.classList.contains('active')) panel.style.display = 'none';
                panel.removeEventListener('transitionend', hide);
            });
        }
    });
}

/* ─────────────────────────────────────────────────────────────
   TOAST NOTIFICATIONS
───────────────────────────────────────────────────────────── */
function showToast(message, type = 'default', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = { success: '✓', error: '✕', warning: '⚠', default: 'ℹ' };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.default}</span><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('out');
        toast.addEventListener('animationend', () => toast.remove());
    }, duration);
}

/* ─────────────────────────────────────────────────────────────
   STATS
───────────────────────────────────────────────────────────── */
async function loadDashboardStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        const set = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.innerText = value ?? 0;
        };
        set('statTotal',     data.total_emails);
        set('statImportant', data.important_today);
        set('statAction',    data.action_required);
        set('statUrgent',    data.urgent);
        set('statReview',    data.needs_review);
        set('statDeadlines', data.upcoming_deadlines);

        // Update review badge
        const badge = document.getElementById('reviewBadge');
        const reviewCount = data.needs_review || 0;
        if (badge) {
            badge.style.display = reviewCount > 0 ? 'inline-flex' : 'none';
            badge.textContent = reviewCount;
        }

        // Update settings badge
        const settingsBadge = document.getElementById('settingsModelBadge');
        if (settingsBadge && data.active_model) settingsBadge.textContent = data.active_model;
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

/* ─────────────────────────────────────────────────────────────
   REVIEW QUEUE
───────────────────────────────────────────────────────────── */
async function loadReviewQueue() {
    const container = document.getElementById('reviewQueueContainer');
    if (!container) return;

    container.innerHTML = renderSkeleton(3);

    try {
        const res = await fetch('/api/review');
        const emails = await res.json();

        if (emails.length === 0) {
            container.innerHTML = renderEmptyState('All caught up!', 'No emails waiting for a decision.');
            return;
        }

        container.innerHTML = emails.map(email => renderReviewCard(email)).join('');
    } catch (err) {
        console.error('Error loading review queue:', err);
        container.innerHTML = `<div class="empty-note" style="color:var(--danger);">Failed to load review queue.</div>`;
    }
}

function renderReviewCard(email) {
    const cls = email.classification || {};
    const priority = cls.priority || 'NORMAL';
    const category = cls.category || 'OTHER';
    const action = cls.action_status || 'NO_ACTION';
    const reasons = JSON.parse(cls.reasons_json || '[]');
    const initials = (email.sender_name || email.sender_email || '?')[0].toUpperCase();

    return `
    <div class="email-card" id="email-card-${email.id}">
      <div class="email-header">
        <div class="email-sender-wrap">
          <div class="sender-avatar">${initials}</div>
          <div>
            <div class="email-sender">${escapeHtml(email.sender_name || email.sender_email)}</div>
            <div class="email-sender-email">${escapeHtml(email.sender_email)}</div>
          </div>
        </div>
        <span class="email-date">${formatDate(email.date_received)}</span>
      </div>
      <div class="email-subject">${escapeHtml(email.subject)}</div>
      <div class="email-preview">${escapeHtml(email.normalized_body ? email.normalized_body.substring(0, 220) : 'No preview available.')}</div>
      <div class="tag-list">
        <span class="tag tag-${priority.toLowerCase()}">⚡ ${priority}</span>
        <span class="tag tag-career">📁 ${category}</span>
        <span class="tag tag-action">✓ ${action}</span>
        <span class="tag">🎯 ${Math.round((cls.confidence || 0) * 100)}%</span>
      </div>
      ${reasons.length ? `
      <div class="explainability-box">
        <strong>Why predicted this way?</strong>
        <ul>${reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
      </div>` : ''}
      <div class="decision-actions">
        <span style="font-size:12px;color:var(--muted);font-weight:500;">Scope:</span>
        <select id="scope-${email.id}" class="scope-select">
          <option value="THIS_EMAIL">Only this email</option>
          <option value="THIS_SENDER">All from this sender</option>
          <option value="SIMILAR_SUBJECTS">Similar subjects</option>
        </select>
        <button class="btn-accept" onclick="submitDecision(${email.id}, '${priority}', '${category}', '${action}')">
          ✓ Accept
        </button>
        <button class="btn-change" onclick="showChangeModal(${email.id}, '${priority}', '${category}', '${action}')">
          ✏️ Change &amp; Teach
        </button>
      </div>
    </div>`;
}

/* ─────────────────────────────────────────────────────────────
   INBOX TAB
───────────────────────────────────────────────────────────── */
let _allInboxEmails = [];

async function loadInboxTab() {
    const container = document.getElementById('inboxContainer');
    if (!container) return;

    container.innerHTML = renderSkeleton(5);

    try {
        const res = await fetch('/api/important');
        _allInboxEmails = await res.json();
        renderInboxList(_allInboxEmails, container);
    } catch (err) {
        console.error('Error loading inbox:', err);
        container.innerHTML = `<div class="empty-note" style="color:var(--danger);">Failed to load inbox.</div>`;
    }
}

function filterInbox(filter) {
    const container = document.getElementById('inboxContainer');
    if (!container) return;

    let filtered = _allInboxEmails;
    if (filter !== 'all') {
        filtered = _allInboxEmails.filter(e => {
            const priority = (e.classification?.priority || '').toLowerCase();
            return priority === filter;
        });
    }
    renderInboxList(filtered, container);
}

function renderInboxList(emails, container) {
    if (!emails.length) {
        container.innerHTML = renderEmptyState('No emails', 'No emails match this filter.');
        return;
    }
    container.innerHTML = emails.map(email => `
    <div class="email-card">
      <div class="email-header">
        <div class="email-sender-wrap">
          <div class="sender-avatar">${(email.sender_name || email.sender_email || '?')[0].toUpperCase()}</div>
          <div>
            <div class="email-sender">${escapeHtml(email.sender_name || email.sender_email)}</div>
            <div class="email-sender-email">${escapeHtml(email.sender_email || '')}</div>
          </div>
        </div>
        <span class="email-date">${formatDate(email.date_received, true)}</span>
      </div>
      <div class="email-subject">${escapeHtml(email.subject)}</div>
      <div class="tag-list">
        <span class="tag tag-${(email.classification?.priority || '').toLowerCase()}">${email.classification?.priority || ''}</span>
        <span class="tag tag-career">${email.classification?.category || ''}</span>
      </div>
    </div>`).join('');
}

/* ─────────────────────────────────────────────────────────────
   TODAY IMPORTANT (Overview tab)
───────────────────────────────────────────────────────────── */
async function loadTodayImportant() {
    const container = document.getElementById('todayImportantContainer');
    if (!container) return;

    try {
        const res = await fetch('/api/important');
        const emails = await res.json();

        if (emails.length === 0) {
            container.innerHTML = renderEmptyState('No important mail yet', '');
            return;
        }

        container.innerHTML = emails.slice(0, 8).map(email => `
        <div class="email-card">
          <div class="email-header">
            <div class="email-sender-wrap">
              <div class="sender-avatar">${(email.sender_name || email.sender_email || '?')[0].toUpperCase()}</div>
              <span class="email-sender">${escapeHtml(email.sender_name || email.sender_email)}</span>
            </div>
            <span class="email-date">${formatDate(email.date_received, true)}</span>
          </div>
          <div class="email-subject">${escapeHtml(email.subject)}</div>
          <div class="tag-list">
            <span class="tag tag-${(email.classification?.priority || '').toLowerCase()}">${email.classification?.priority}</span>
            <span class="tag tag-career">${email.classification?.category}</span>
          </div>
        </div>`).join('');
    } catch (err) {
        console.error('Error loading important emails:', err);
    }
}

/* ─────────────────────────────────────────────────────────────
   DECISIONS
───────────────────────────────────────────────────────────── */
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
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.97)';
                setTimeout(() => card.remove(), 320);
            }
            showToast('Decision saved ✓', 'success');
            loadDashboardStats();
        } else {
            showToast('Failed to submit decision.', 'error');
        }
    } catch (err) {
        console.error('Error submitting decision:', err);
        showToast('Network error. Please try again.', 'error');
    }
}

/* ─────────────────────────────────────────────────────────────
   CHANGE & TEACH MODAL
───────────────────────────────────────────────────────────── */
function showChangeModal(emailId, currentPriority, currentCategory, currentAction) {
    document.getElementById('modalEmailId').value = emailId;
    document.getElementById('modalPriority').value = currentPriority;
    document.getElementById('modalCategory').value = currentCategory;
    document.getElementById('modalAction').value = currentAction;

    const overlay = document.getElementById('changeModal');
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');

    // Focus first select
    setTimeout(() => document.getElementById('modalPriority').focus(), 50);
}

function closeChangeModal() {
    const overlay = document.getElementById('changeModal');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
}

function confirmChangeModal() {
    const emailId   = document.getElementById('modalEmailId').value;
    const priority  = document.getElementById('modalPriority').value;
    const category  = document.getElementById('modalCategory').value;
    const action    = document.getElementById('modalAction').value;
    closeChangeModal();
    submitDecision(parseInt(emailId, 10), priority, category, action);
}

/* ─────────────────────────────────────────────────────────────
   SYNC
───────────────────────────────────────────────────────────── */
async function runManualSync() {
    const syncBtn = document.getElementById('syncBtn');
    const originalHTML = syncBtn.innerHTML;

    syncBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="width:14px;height:14px;animation:spin 0.8s linear infinite">
        <polyline points="23 4 23 10 17 10"/>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
      </svg>
      Syncing…`;
    syncBtn.disabled = true;

    // Add spin keyframe if not present
    if (!document.getElementById('spinStyle')) {
        const s = document.createElement('style');
        s.id = 'spinStyle';
        s.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
        document.head.appendChild(s);
    }

    try {
        const res = await fetch('/api/sync', { method: 'POST' });
        const data = await res.json();
        showToast(`Synced ${data.processed_count || 0} messages${data.dry_run ? ' (dry run)' : ''}`, 'success');
        loadDashboardStats();
        loadReviewQueue();
        loadTodayImportant();
        loadInboxTab();
        if (window.refreshCoworkerAfterSync) window.refreshCoworkerAfterSync();
    } catch (err) {
        showToast('Sync failed — check Gmail auth.', 'error');
    } finally {
        syncBtn.innerHTML = originalHTML;
        syncBtn.disabled = false;
    }
}

/* ─────────────────────────────────────────────────────────────
   HELPERS
───────────────────────────────────────────────────────────── */
function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatDate(dateStr, timeOnly = false) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (timeOnly) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const today = new Date();
    const isToday = d.toDateString() === today.toDateString();
    if (isToday) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function renderSkeleton(count = 3) {
    const card = `
    <div class="email-card" style="animation:pulse 1.5s ease-in-out infinite;">
      <div style="height:12px;width:40%;background:var(--surface-3);border-radius:4px;margin-bottom:8px;"></div>
      <div style="height:14px;width:70%;background:var(--surface-3);border-radius:4px;margin-bottom:6px;"></div>
      <div style="height:12px;width:90%;background:var(--surface-3);border-radius:4px;"></div>
    </div>`;

    if (!document.getElementById('pulseStyle')) {
        const s = document.createElement('style');
        s.id = 'pulseStyle';
        s.textContent = '@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }';
        document.head.appendChild(s);
    }
    return Array(count).fill(card).join('');
}

function renderEmptyState(title, subtitle) {
    return `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M9 11l3 3L22 4"/>
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
      </svg>
      <strong>${escapeHtml(title)}</strong>
      ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}
    </div>`;
}

/* ─────────────────────────────────────────────────────────────
   SETTINGS MODE TOGGLE
───────────────────────────────────────────────────────────── */
async function toggleRunMode(clickedSource, isChecked) {
    const dryRunInput = document.getElementById('settingDryRun');
    const liveInput = document.getElementById('settingLive');
    
    // Determine target mode
    let targetMode = 'dry_run';
    if (clickedSource === 'dry_run') {
        targetMode = isChecked ? 'dry_run' : 'live';
    } else {
        targetMode = isChecked ? 'live' : 'dry_run';
    }

    try {
        const res = await fetch('/api/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: targetMode }),
        });

        const data = await res.json();
        if (data.status === 'success') {
            const isDry = data.dry_run;
            if (dryRunInput) dryRunInput.checked = isDry;
            if (liveInput) liveInput.checked = !isDry;
            
            // Update topbar status badge if present
            const statusBadge = document.querySelector('.status-indicator');
            if (statusBadge) {
                statusBadge.innerHTML = isDry 
                    ? `<span class="status-dot warning"></span> Dry run` 
                    : `<span class="status-dot success"></span> Live mode`;
            }

            toast(isDry ? 'Switched to Dry Run mode' : '⚡ Bật Live Mode thành công! Gmail nhãn sẽ được ghi trực tiếp.', 'success');
        } else {
            throw new Error(data.detail || 'Failed to update mode');
        }
    } catch (err) {
        console.error('Mode toggle error:', err);
        toast('Không thể chuyển đổi Run Mode: ' + err.message, 'error');
        // Revert inputs
        if (dryRunInput && liveInput) {
            dryRunInput.checked = !dryRunInput.checked;
            liveInput.checked = !liveInput.checked;
        }
    }
}

