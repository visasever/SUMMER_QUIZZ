let adminToken = localStorage.getItem('admin_token') || '';

document.addEventListener('DOMContentLoaded', () => {
  if (!adminToken) {
    window.location.href = '/login.html';
    return;
  }

  setupAdminEvents();
  loadSettings();
  loadLeads();
  loadUploadedFiles();
});

function setupAdminEvents() {
  const settingsForm = document.getElementById('settings-form');
  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        branch_name: document.getElementById('set_branch_name').value,
        youtube_url: document.getElementById('set_youtube_url').value,
        phone: document.getElementById('set_phone').value,
        email: document.getElementById('set_email').value,
        address: document.getElementById('set_address').value,
        telegram: document.getElementById('set_telegram').value,
        email_api_key: document.getElementById('set_email_api_key').value,
        smtp_host: document.getElementById('set_smtp_host').value,
        smtp_port: document.getElementById('set_smtp_port').value,
        smtp_user: document.getElementById('set_smtp_user').value,
        smtp_pass: document.getElementById('set_smtp_pass').value
      };

      if (payload.youtube_url) {
        localStorage.setItem('youtube_url', payload.youtube_url);
      }
      try {
        const res = await fetch('/api/admin/settings', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${adminToken}`
          },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('Налаштування філії та пошти успішно збережено!');
        } else {
          alert('Збережено локально. (Увага: сервер повернув помилку або не підключений)');
        }
      } catch (err) {
        alert('Збережено локально!');
      }
    });
  }

  const testSmtpBtn = document.getElementById('test-smtp-btn');
  if (testSmtpBtn) {
    testSmtpBtn.addEventListener('click', async () => {
      testSmtpBtn.disabled = true;
      testSmtpBtn.textContent = '⏳ Перевірка...';
      try {
        const res = await fetch('/api/admin/test-email', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${adminToken}`
          },
          body: JSON.stringify({
            email_api_key: document.getElementById('set_email_api_key').value,
            smtp_host: document.getElementById('set_smtp_host').value,
            smtp_port: document.getElementById('set_smtp_port').value,
            smtp_user: document.getElementById('set_smtp_user').value,
            smtp_pass: document.getElementById('set_smtp_pass').value
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`✅ УСПІХ! Тестовий лист успішно надіслано на ${data.email}!\nПеревірте скриньку вхідних.`);
        } else {
          alert(`❌ ПОМИЛКА ВІДПРАВКИ ПОШТИ:\n${data.error || 'Невідома помилка підключення'}`);
        }
      } catch (err) {
        alert(`❌ Помилка з'єднання із сервером: ${err.message}`);
      } finally {
        testSmtpBtn.disabled = false;
        testSmtpBtn.textContent = '🧪 Протестувати пошту';
      }
    });
  }

  const uploadForm = document.getElementById('upload-file-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('upload-file-input');
      const fileType = document.getElementById('upload-file-type').value;

      if (!fileInput.files || fileInput.files.length === 0) {
        alert('Оберіть файл для завантаження');
        return;
      }

      const formData = new FormData();
      formData.append('file_type', fileType);
      formData.append('file', fileInput.files[0]);

      try {
        const res = await fetch('/api/admin/upload', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${adminToken}`
          },
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`Файл ${data.original_name} успішно завантажено!`);
          loadUploadedFiles();
        } else {
          alert(data.error || 'Помилка завантаження файла');
        }
      } catch (err) {
        alert('Помилка сервера при завантаженні');
      }
    });
  }

  const exportBtn = document.getElementById('export-csv-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      window.location.href = `/api/admin/leads/export?pwd=${encodeURIComponent(adminToken)}`;
    });
  }

  const logoutBtn = document.getElementById('admin-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      localStorage.removeItem('admin_token');
      window.location.href = '/login.html';
    });
  }

  const searchInput = document.getElementById('leads-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterLeadsTable(e.target.value.toLowerCase());
    });
  }

  const tbody = document.getElementById('leads-tbody');
  if (tbody) {
    tbody.addEventListener('click', async (e) => {
      const deleteBtn = e.target.closest('.btn-delete-lead');
      if (deleteBtn) {
        const leadId = deleteBtn.dataset.id;
        const childName = deleteBtn.dataset.name || `#${leadId}`;
        if (confirm(`Ви дійсно бажаєте видалити запис про учасника "${childName}" (ID #${leadId}) з бази даних?`)) {
          try {
            const res = await fetch('/api/admin/leads/delete', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${adminToken}`
              },
              body: JSON.stringify({ id: leadId })
            });
            const data = await res.json();
            if (res.ok && data.success) {
              loadLeads();
            } else {
              alert(data.error || 'Помилка при видаленні запису');
            }
          } catch (err) {
            alert('Помилка сервера при видаленні');
          }
        }
      }
    });
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('set_branch_name').value = data.branch_name || '';
      document.getElementById('set_youtube_url').value = data.youtube_url || localStorage.getItem('youtube_url') || '';
      document.getElementById('set_phone').value = data.phone || '';
      document.getElementById('set_email').value = data.email || '';
      document.getElementById('set_address').value = data.address || '';
      document.getElementById('set_telegram').value = data.telegram || '';
      document.getElementById('set_email_api_key').value = data.email_api_key || '';
      document.getElementById('set_smtp_host').value = data.smtp_host || '';
      document.getElementById('set_smtp_port').value = data.smtp_port || '';
      document.getElementById('set_smtp_user').value = data.smtp_user || '';
      document.getElementById('set_smtp_pass').value = data.smtp_pass || '';
    }
  } catch (err) {
    console.error(err);
  }
}

let loadedLeads = [];

async function loadLeads() {
  try {
    const res = await fetch('/api/admin/leads', {
      headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      loadedLeads = data.leads || [];
      renderLeadsTable(loadedLeads);
    } else if (res.status === 401) {
      localStorage.removeItem('admin_token');
      window.location.href = '/login.html';
    }
  } catch (err) {
    console.error(err);
  }
}

function renderLeadsTable(leads) {
  const tbody = document.getElementById('leads-tbody');
  tbody.innerHTML = '';

  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:#94a3b8; padding:24px;">Заявок поки немає</td></tr>`;
    return;
  }

  leads.forEach(lead => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${lead.id}</td>
      <td>${lead.created_at}</td>
      <td><strong>${lead.child_name}</strong> (${lead.child_age} р.)</td>
      <td>${lead.city}</td>
      <td>${lead.parent_name}</td>
      <td><a href="tel:${lead.parent_phone}" style="color:#38bdf8; text-decoration:none;">${lead.parent_phone}</a></td>
      <td>${lead.parent_email}</td>
      <td><span class="ticket-tag">${lead.ticket_number}</span></td>
      <td><span style="color:#ffb703; font-weight:600;">${lead.result_profile}</span></td>
      <td style="text-align: center;">
        <button class="btn-delete-lead" data-id="${lead.id}" data-name="${lead.child_name}" title="Видалити запис" style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; cursor: pointer; font-size: 0.95rem; padding: 6px 10px; border-radius: 6px; transition: all 0.2s;">
          🗑️
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterLeadsTable(query) {
  if (!query) {
    renderLeadsTable(loadedLeads);
    return;
  }
  const filtered = loadedLeads.filter(l => 
    l.child_name.toLowerCase().includes(query) ||
    l.parent_name.toLowerCase().includes(query) ||
    l.parent_phone.toLowerCase().includes(query) ||
    l.parent_email.toLowerCase().includes(query) ||
    l.ticket_number.toLowerCase().includes(query) ||
    l.city.toLowerCase().includes(query)
  );
  renderLeadsTable(filtered);
}

async function loadUploadedFiles() {
  try {
    const res = await fetch('/api/admin/files');
    if (res.ok) {
      const files = await res.json();
      const listEl = document.getElementById('uploaded-files-list');
      listEl.innerHTML = '';
      
      const fileTypes = {
        'cert_template': 'Шаблон Сертифіката',
        'parent_guide': 'IT-гайд для батьків'
      };

      for (const [type, label] of Object.entries(fileTypes)) {
        const fileInfo = files[type];
        const item = document.createElement('div');
        item.style.cssText = 'padding:12px; background:#0f172a; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;';
        if (fileInfo) {
          item.innerHTML = `
            <div>
              <strong>${label}</strong>: ${fileInfo.original_name}
              <div style="font-size:0.8rem; color:#94a3b8;">Завантажено: ${fileInfo.uploaded_at}</div>
            </div>
            <a href="/api/files/download?type=${type}" class="btn-admin" style="font-size:0.85rem; padding:6px 12px; text-decoration:none;">Завантажити</a>
          `;
        } else {
          item.innerHTML = `
            <div>
              <strong>${label}</strong>: <span style="color:#94a3b8;">Файл ще не завантажено</span>
            </div>
          `;
        }
        listEl.appendChild(item);
      }
    }
  } catch (err) {
    console.error(err);
  }
}
