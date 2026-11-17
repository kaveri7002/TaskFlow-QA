const API_URL = window.TASKFLOW_API_URL || '';
const STORAGE_KEY = 'taskflow-token';
const statuses = [
  { id: 'todo', label: 'To do', color: 'blue' },
  { id: 'in_progress', label: 'In progress', color: 'amber' },
  { id: 'completed', label: 'Completed', color: 'green' },
];
const state = { token: localStorage.getItem(STORAGE_KEY), user: null, tasks: [], search: '', priority: '' };
const app = document.querySelector('#app');

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(`${API_URL}/api${path}`, { ...options, headers });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && state.token) signOut();
    throw new Error(result.error || `Request failed (${response.status}).`);
  }
  return result;
}

function renderAuth(mode = 'login', message = '') {
  const isRegister = mode === 'register';
  app.innerHTML = `
    <main class="auth-shell">
      <section class="auth-intro">
        <a class="brand brand-light" href="#"><span class="brand-mark">T</span> taskflow<span>qa</span></a>
        <div class="intro-copy">
          <p class="eyebrow">YOUR WORK, IN FLOW</p>
          <h1>Make good work<br>feel <em>effortless.</em></h1>
          <p>A thoughtful space for your team's tasks, testing, and next big release.</p>
          <div class="intro-proof"><span class="avatar-stack"><b>JD</b><b>AK</b><b>ML</b></span><span>Small steps. Excellent software.</span></div>
        </div>
        <span class="intro-orbit orbit-one"></span><span class="intro-orbit orbit-two"></span>
        <p class="intro-foot">PROJECT MANAGEMENT, WITH QUALITY BUILT IN</p>
      </section>
      <section class="auth-panel">
        <div class="auth-box">
          <span class="mobile-brand brand"><span class="brand-mark">T</span> taskflow<span>qa</span></span>
          <p class="eyebrow">WELCOME ${isRegister ? 'ABOARD' : 'BACK'}</p>
          <h2>${isRegister ? 'Create your account' : 'Sign in to your space'}</h2>
          <p class="muted">${isRegister ? 'Start organizing work that ships with confidence.' : 'Your team’s next great release starts here.'}</p>
          <div class="auth-tabs" role="tablist">
            <button type="button" class="${!isRegister ? 'active' : ''}" data-mode="login">Sign in</button>
            <button type="button" class="${isRegister ? 'active' : ''}" data-mode="register">Create account</button>
          </div>
          <form id="auth-form">
            ${isRegister ? '<label>Your name<input name="name" autocomplete="name" placeholder="Alex Morgan" maxlength="80" required></label>' : ''}
            <label>Email address<input name="email" type="email" autocomplete="email" placeholder="you@company.com" maxlength="254" required></label>
            <label>Password<input name="password" type="password" autocomplete="${isRegister ? 'new-password' : 'current-password'}" placeholder="${isRegister ? 'At least 8 characters' : 'Enter your password'}" minlength="${isRegister ? 8 : 1}" maxlength="128" required></label>
            <p class="form-message" role="alert">${escapeHtml(message)}</p>
            <button class="button button-primary auth-submit" type="submit">${isRegister ? 'Create account' : 'Sign in'} <span>→</span></button>
          </form>
          <p class="auth-terms">Your workspace is private. Your tasks belong to you.</p>
        </div>
      </section>
    </main>`;
  app.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => renderAuth(button.dataset.mode));
  });
  app.querySelector('#auth-form').addEventListener('submit', submitAuth);
}

async function submitAuth(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const submit = form.querySelector('button[type="submit"]');
  const message = form.querySelector('.form-message');
  submit.disabled = true;
  submit.textContent = 'Please wait…';
  try {
    const isRegister = Boolean(data.name);
    const result = await api(`/auth/${isRegister ? 'register' : 'login'}`, {
      method: 'POST', body: JSON.stringify(data),
    });
    state.token = result.token;
    state.user = result.user;
    localStorage.setItem(STORAGE_KEY, state.token);
    await loadBoard();
  } catch (error) {
    message.textContent = error.message;
    submit.disabled = false;
    submit.innerHTML = `${data.name ? 'Create account' : 'Sign in'} <span>→</span>`;
  }
}

function signOut() {
  state.token = null;
  state.user = null;
  state.tasks = [];
  localStorage.removeItem(STORAGE_KEY);
  renderAuth('login');
}

function dateLabel(dateString) {
  if (!dateString) return 'No due date';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(`${dateString}T12:00:00`));
}

function taskCard(task) {
  const priorityLabel = task.priority[0].toUpperCase() + task.priority.slice(1);
  return `<article class="task-card" draggable="true" data-task-id="${task.id}" aria-label="${escapeHtml(task.title)}">
    <div class="task-top"><span class="priority priority-${task.priority}"><i></i>${priorityLabel}</span>
      <div class="task-actions"><button class="icon-button" data-edit="${task.id}" aria-label="Edit ${escapeHtml(task.title)}" title="Edit task">✎</button><button class="icon-button danger-hover" data-delete="${task.id}" aria-label="Delete ${escapeHtml(task.title)}" title="Delete task">×</button></div></div>
    <h3>${escapeHtml(task.title)}</h3>
    ${task.description ? `<p class="task-description">${escapeHtml(task.description)}</p>` : ''}
    <div class="task-footer"><span class="due-date ${task.due_date && task.due_date < new Date().toISOString().slice(0, 10) && task.status !== 'completed' ? 'overdue' : ''}"><span>◷</span>${dateLabel(task.due_date)}</span><span class="task-assignee" title="${escapeHtml(state.user.name)}">${escapeHtml(state.user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase())}</span></div>
  </article>`;
}

function renderBoard() {
  const visible = state.tasks.filter((task) => {
    const text = `${task.title} ${task.description}`.toLowerCase();
    return text.includes(state.search.toLowerCase()) && (!state.priority || task.priority === state.priority);
  });
  const completed = state.tasks.filter((task) => task.status === 'completed').length;
  app.innerHTML = `
    <div class="workspace">
      <aside class="sidebar">
        <a class="brand" href="#"><span class="brand-mark">T</span> taskflow<span>qa</span></a>
        <div class="workspace-label">WORKSPACE</div>
        <button class="side-link selected"><span class="side-icon">▦</span> My board <span class="side-count">${state.tasks.length}</span></button>
        <div class="sidebar-bottom"><div class="upgrade-card"><span class="sparkle">✳</span><strong>Good work, in motion.</strong><p>Keep your team aligned and your quality high.</p></div>
          <button class="profile-button account-settings" aria-label="Account settings"><span class="profile-avatar">${escapeHtml(state.user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase())}</span><span class="profile-copy"><strong>${escapeHtml(state.user.name)}</strong><small>${escapeHtml(state.user.email)}</small></span><span class="profile-menu">···</span></button>
          <button class="logout-button" id="logout">Sign out</button>
        </div>
      </aside>
      <main class="main-content">
        <header class="topbar"><div class="breadcrumbs">Workspace <span>/</span> <strong>My board</strong></div><div class="topbar-right"><span class="online-dot"></span><span>All changes saved</span><button class="top-avatar account-settings" aria-label="Account settings">${escapeHtml(state.user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase())}</button></div></header>
        <section class="board-content">
          <div class="welcome-row"><div><p class="eyebrow">MONDAY, LET'S MAKE IT COUNT</p><h1>Your work, <em>in flow.</em></h1><p class="muted">A clear view of what's moving and what comes next.</p></div><button class="button button-primary" id="new-task"><span>＋</span> New task</button></div>
          <div class="summary-row"><div class="summary-card"><span class="summary-icon icon-tasks">▤</span><div><strong>${state.tasks.length}</strong><span>Total tasks</span></div><span class="summary-trend">in your workspace</span></div><div class="summary-card"><span class="summary-icon icon-progress">↗</span><div><strong>${state.tasks.filter((task) => task.status === 'in_progress').length}</strong><span>In progress</span></div><span class="summary-trend">moving forward</span></div><div class="summary-card"><span class="summary-icon icon-done">✓</span><div><strong>${completed}</strong><span>Completed</span></div><span class="summary-trend">${state.tasks.length ? Math.round((completed / state.tasks.length) * 100) : 0}% of all tasks</span></div></div>
          <div class="board-heading"><div><h2>Project board <span class="live-pill"><i></i> LIVE</span></h2><p>Drag a card to move it between stages.</p></div><div class="board-tools"><label class="search-box"><span>⌕</span><input id="search" type="search" placeholder="Search tasks..." value="${escapeHtml(state.search)}" aria-label="Search tasks"><kbd>⌘ K</kbd></label><select id="priority-filter" aria-label="Filter by priority"><option value="">All priorities</option><option value="high" ${state.priority === 'high' ? 'selected' : ''}>High priority</option><option value="medium" ${state.priority === 'medium' ? 'selected' : ''}>Medium priority</option><option value="low" ${state.priority === 'low' ? 'selected' : ''}>Low priority</option></select></div></div>
          <section class="board" aria-label="Task board">
            ${statuses.map((status) => {
              const tasks = visible.filter((task) => task.status === status.id);
              return `<section class="board-column" data-status="${status.id}" aria-label="${status.label} tasks"><header class="column-header"><span class="column-dot dot-${status.color}"></span><h3>${status.label}</h3><span class="column-count">${tasks.length}</span><button class="column-add" data-add-status="${status.id}" aria-label="Add task to ${status.label}">＋</button></header><div class="task-list">${tasks.length ? tasks.map(taskCard).join('') : `<div class="empty-column"><span>${status.id === 'completed' ? '✳' : '↳'}</span><p>${state.search || state.priority ? 'No matching tasks' : 'Nothing here yet'}</p><small>${state.search || state.priority ? 'Try another filter.' : 'Add a task or drag one here.'}</small></div>`}</div></section>`;
            }).join('')}
          </section>
          <footer class="board-foot"><span>Showing ${visible.length} of ${state.tasks.length} tasks</span><span><i class="online-dot"></i> Synced with your workspace</span></footer>
        </section>
      </main>
      <dialog id="task-dialog" class="task-dialog"><form id="task-form" method="dialog"><div class="dialog-heading"><div><p class="eyebrow">TASK DETAILS</p><h2 id="dialog-title">Create a task</h2></div><button type="button" class="icon-button dialog-close" aria-label="Close dialog">×</button></div><input type="hidden" name="id"><label>Task name<input name="title" maxlength="160" placeholder="e.g. Test checkout flow" required></label><label>Description <span class="optional">(optional)</span><textarea name="description" maxlength="2000" rows="3" placeholder="What needs to be done?"></textarea></label><div class="dialog-grid"><label>Status<select name="status"><option value="todo">To do</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></label><label>Priority<select name="priority"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option></select></label></div><label>Due date <span class="optional">(optional)</span><input name="due_date" type="date"></label><p class="form-message" role="alert"></p><div class="dialog-actions"><button type="button" class="button button-quiet dialog-cancel">Cancel</button><button type="submit" class="button button-primary">Save task <span>→</span></button></div></form></dialog>
      <dialog id="account-dialog" class="task-dialog settings-dialog"><form id="account-form"><div class="dialog-heading"><div><p class="eyebrow">ACCOUNT SETTINGS</p><h2>Change email or password</h2></div><button type="button" class="icon-button account-dialog-close" aria-label="Close account settings">×</button></div><p class="muted">Enter your current password to confirm any changes.</p><label>New email address <span class="optional">(optional)</span><input name="email" type="email" maxlength="254" autocomplete="email" placeholder="${escapeHtml(state.user.email)}"></label><label>New password <span class="optional">(optional)</span><input name="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" placeholder="At least 8 characters"></label><label>Current password<input name="current_password" type="password" required autocomplete="current-password"></label><p class="form-message" role="alert" aria-live="polite"></p><div class="dialog-actions"><button type="button" class="button button-quiet account-dialog-cancel">Cancel</button><button type="submit" class="button button-primary">Save changes <span>→</span></button></div></form></dialog>
    </div>`;
  wireBoard();
}

function showTaskDialog(task = null, status = 'todo') {
  const dialog = app.querySelector('#task-dialog');
  const form = app.querySelector('#task-form');
  form.reset();
  form.elements.id.value = task?.id || '';
  form.elements.title.value = task?.title || '';
  form.elements.description.value = task?.description || '';
  form.elements.status.value = task?.status || status;
  form.elements.priority.value = task?.priority || 'medium';
  form.elements.due_date.value = task?.due_date || '';
  form.querySelector('.form-message').textContent = '';
  app.querySelector('#dialog-title').textContent = task ? 'Edit task' : 'Create a task';
  dialog.showModal();
  form.elements.title.focus();
}

function wireBoard() {
  app.querySelector('#logout').addEventListener('click', signOut);
  app.querySelectorAll('.account-settings').forEach((button) => button.addEventListener('click', showAccountDialog));
  app.querySelector('#new-task').addEventListener('click', () => showTaskDialog());
  app.querySelectorAll('[data-add-status]').forEach((button) => button.addEventListener('click', () => showTaskDialog(null, button.dataset.addStatus)));
  app.querySelectorAll('[data-edit]').forEach((button) => button.addEventListener('click', () => showTaskDialog(state.tasks.find((task) => task.id === Number(button.dataset.edit)))));
  app.querySelectorAll('[data-delete]').forEach((button) => button.addEventListener('click', () => deleteTask(Number(button.dataset.delete))));
  app.querySelector('#search').addEventListener('input', (event) => {
    state.search = event.target.value;
    const position = event.target.selectionStart;
    renderBoard();
    const search = app.querySelector('#search');
    search.focus();
    search.setSelectionRange(position, position);
  });
  app.querySelector('#priority-filter').addEventListener('change', (event) => {
    state.priority = event.target.value;
    renderBoard();
  });
  app.querySelector('.dialog-close').addEventListener('click', () => app.querySelector('#task-dialog').close());
  app.querySelector('.dialog-cancel').addEventListener('click', () => app.querySelector('#task-dialog').close());
  app.querySelector('#task-form').addEventListener('submit', saveTask);
  app.querySelector('#account-form').addEventListener('submit', saveAccount);
  app.querySelector('.account-dialog-close').addEventListener('click', () => app.querySelector('#account-dialog').close());
  app.querySelector('.account-dialog-cancel').addEventListener('click', () => app.querySelector('#account-dialog').close());
  app.querySelectorAll('.task-card').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      event.dataTransfer.setData('text/plain', card.dataset.taskId);
      event.dataTransfer.effectAllowed = 'move';
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
  });
  app.querySelectorAll('.board-column').forEach((column) => {
    column.addEventListener('dragover', (event) => {
      event.preventDefault();
      column.classList.add('drag-over');
    });
    column.addEventListener('dragleave', (event) => {
      if (!column.contains(event.relatedTarget)) column.classList.remove('drag-over');
    });
    column.addEventListener('drop', async (event) => {
      event.preventDefault();
      column.classList.remove('drag-over');
      const taskId = Number(event.dataTransfer.getData('text/plain'));
      const task = state.tasks.find((item) => item.id === taskId);
      const status = column.dataset.status;
      if (task && task.status !== status) {
        try {
          await api(`/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify({ status }) });
          await loadBoard();
        } catch (error) { window.alert(error.message); }
      }
    });
  });
  app.querySelector('.search-box kbd').addEventListener('click', () => app.querySelector('#search').focus());
  window.removeEventListener('keydown', handleShortcut);
  window.addEventListener('keydown', handleShortcut);
}

function showAccountDialog() {
  const dialog = app.querySelector('#account-dialog');
  const form = app.querySelector('#account-form');
  form.reset();
  form.elements.email.placeholder = state.user.email;
  form.querySelector('.form-message').textContent = '';
  form.querySelector('.form-message').classList.remove('success-message');
  dialog.showModal();
  form.elements.email.focus();
}

async function saveAccount(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = form.querySelector('.form-message');
  const submit = form.querySelector('button[type="submit"]');
  const email = form.elements.email.value.trim();
  const password = form.elements.password.value;
  if (!email && !password) {
    message.textContent = 'Enter a new email address or password.';
    return;
  }

  const payload = { current_password: form.elements.current_password.value };
  if (email) payload.email = email;
  if (password) payload.password = password;
  submit.disabled = true;
  message.textContent = '';
  message.classList.remove('success-message');
  try {
    const result = await api('/auth/account', { method: 'PATCH', body: JSON.stringify(payload) });
    state.user = result.user;
    form.elements.email.value = '';
    form.elements.email.placeholder = state.user.email;
    form.elements.password.value = '';
    form.elements.current_password.value = '';
    message.textContent = 'Your account details have been updated.';
    message.classList.add('success-message');
    app.querySelector('.profile-copy small').textContent = state.user.email;
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

function handleShortcut(event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && app.querySelector('#search')) {
    event.preventDefault();
    app.querySelector('#search').focus();
  }
}

async function saveTask(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const id = form.elements.id.value;
  const payload = {
    title: form.elements.title.value,
    description: form.elements.description.value,
    status: form.elements.status.value,
    priority: form.elements.priority.value,
    due_date: form.elements.due_date.value || null,
  };
  const submit = form.querySelector('button[type="submit"]');
  const message = form.querySelector('.form-message');
  submit.disabled = true;
  try {
    await api(`/tasks${id ? `/${id}` : ''}`, { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
    app.querySelector('#task-dialog').close();
    await loadBoard();
  } catch (error) {
    message.textContent = error.message;
  } finally { submit.disabled = false; }
}

async function deleteTask(id) {
  if (!window.confirm('Delete this task? This cannot be undone.')) return;
  try {
    await api(`/tasks/${id}`, { method: 'DELETE' });
    await loadBoard();
  } catch (error) { window.alert(error.message); }
}

async function loadBoard() {
  try {
    const [userResult, taskResult] = await Promise.all([api('/auth/me'), api('/tasks')]);
    state.user = userResult.user;
    state.tasks = taskResult.tasks;
    window.removeEventListener('keydown', handleShortcut);
    renderBoard();
  } catch (error) {
    if (state.token) {
      localStorage.removeItem(STORAGE_KEY);
      state.token = null;
    }
    renderAuth('login', error.message === 'Sign in to continue.' ? '' : `Could not connect: ${error.message}`);
  }
}

if (state.token) loadBoard();
else renderAuth();
