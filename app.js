const state = {
  sales: [],
  products: [],
  expenses: [],
  inventoryMovements: [],
  inventoryHistory: [],
  openAccounts: [],
  cashRegister: {
    status: 'CLOSED',
    session: null
  },
  currentUser: null,
  users: [],
  suppliers: [],
  purchases: []
};

const API_BASE = '';

const AUTH_TOKEN_KEY =
  'lp-auth-token';

const AUTH_USER_KEY =
  'lp-auth-user';



const money = n =>
  new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0
  }).format(Number(n) || 0);

const app = document.querySelector('#app');

const toast = message => {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.classList.add('show');

  setTimeout(() => {
    element.classList.remove('show');
  }, 2400);
};


function getAdminKey() {
  let key = sessionStorage.getItem(
    'lp-admin-key'
  );

  if (!key) {
    key = window.prompt(
      'Ingresa la clave de administrador'
    );

    if (key) {
      sessionStorage.setItem(
        'lp-admin-key',
        key.trim()
      );
    }
  }

  return key?.trim() || '';
}



async function authenticatedFetch(
  url,
  options = {}
) {
  const headers =
    new Headers(
      options.headers || {}
    );

  const response =
    await fetch(
      url,
      {
        ...options,

        headers,

        credentials:
          'include'
      }
    );


  if (
    response.status === 401
  ) {
    logoutUser(
      false
    );

    throw new Error(
      'Tu sesión expiró. Inicia sesión nuevamente.'
    );
  }


  return response;
}



async function adminFetch(
  url,
  options = {}
) {
  const response =
    await authenticatedFetch(
      url,
      options
    );


  if (
    response.status === 403
  ) {
    throw new Error(
      'No tienes permiso para realizar esta acción.'
    );
  }


  return response;
}



/* ============================================================
   AUTHENTICATION
============================================================ */

function getAuthToken() {
  return localStorage.getItem(
    AUTH_TOKEN_KEY
  );
}


function getRoleLabel(role) {
  const labels = {
    ADMIN:
      'Administrador',

    VENDEDOR:
      'Vendedor'
  };

  return (
    labels[role]
    || role
    || 'Usuario'
  );
}


function getUserInitials(
  fullName
) {
  const parts =
    String(
      fullName || ''
    )
      .trim()
      .split(/\s+/)
      .filter(Boolean);

  if (!parts.length) {
    return 'U';
  }

  if (parts.length === 1) {
    return parts[0]
      .slice(0, 2)
      .toUpperCase();
  }

  return (
    parts[0][0]
    + parts[1][0]
  ).toUpperCase();
}



let systemAuditLogs = [];
let systemAuditLoaded = false;


function auditRoleLabel(role) {
  const labels = {
    ADMIN: 'Administrador',
    VENDEDOR: 'Vendedor'
  };

  return labels[role] || role || 'Sistema';
}


function auditActionLabel(action) {
  const labels = {
    PRODUCT_CREATE:
      'Creó producto',

    PRODUCT_DEACTIVATE:
      'Desactivó producto',

    QR_CREATE:
      'Generó QR',

    QR_DELETE:
      'Eliminó QR',

    SALE_CREATE:
      'Registró venta',

    EXPENSE_CREATE:
      'Registró gasto',

    INVENTORY_ADJUSTMENT:
      'Ajustó inventario',

    CASH_OPEN:
      'Abrió caja',

    CASH_CLOSE:
      'Cerró caja',

    USER_CREATE:
      'Creó usuario',

    USER_DEACTIVATE:
      'Desactivó usuario',

    USER_REACTIVATE:
      'Reactivó usuario'
  };

  return (
    labels[action]
    || action
    || 'Actividad'
  );
}


function auditActionIcon(action) {
  const icons = {
    PRODUCT_CREATE: '＋',
    PRODUCT_DEACTIVATE: '−',
    QR_CREATE: 'QR',
    QR_DELETE: '×',
    SALE_CREATE: '$',
    EXPENSE_CREATE: '↘',
    INVENTORY_ADJUSTMENT: '↕',
    CASH_OPEN: '↗',
    CASH_CLOSE: '✓',
    USER_CREATE: '+',
    USER_DEACTIVATE: '−',
    USER_REACTIVATE: '↻'
  };

  return icons[action] || '•';
}


function auditActionCategory(action) {
  if (
    action?.startsWith('PRODUCT')
    || action?.startsWith('QR')
  ) {
    return 'inventory';
  }

  if (action?.startsWith('SALE')) {
    return 'sales';
  }

  if (action?.startsWith('EXPENSE')) {
    return 'expenses';
  }

  if (action?.startsWith('CASH')) {
    return 'cash';
  }

  if (action?.startsWith('USER')) {
    return 'users';
  }

  if (action?.startsWith('INVENTORY')) {
    return 'inventory';
  }

  return 'other';
}


function auditCategoryLabel(action) {
  const category =
    auditActionCategory(action);

  const labels = {
    sales: 'Venta',
    cash: 'Caja',
    inventory: 'Inventario',
    expenses: 'Gasto',
    users: 'Usuario',
    other: 'Sistema'
  };

  return (
    labels[category]
    || 'Sistema'
  );
}


function auditEntityLabel(log) {
  if (
    log.entity_name
    && log.entity_name !== 'Caja'
  ) {
    return log.entity_name;
  }

  if (log.entity_type === 'CASH_REGISTER') {
    return 'Caja';
  }

  return (
    log.entity_name
    || log.entity_type
    || 'Sistema'
  );
}


function auditDate(value) {
  if (!value) {
    return '';
  }

  // El backend guarda datetime.utcnow() sin zona horaria.
  // Si no viene Z/offset, lo interpretamos explícitamente como UTC.
  const normalized =
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
      ? value
      : `${value}Z`;

  const date =
    new Date(normalized);

  const timeZone =
    'America/Bogota';

  const now =
    new Date();

  const dateKey =
    new Intl.DateTimeFormat(
      'en-CA',
      {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }
    ).format(date);

  const todayKey =
    new Intl.DateTimeFormat(
      'en-CA',
      {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }
    ).format(now);

  const yesterday =
    new Date(
      now.getTime()
      - 24 * 60 * 60 * 1000
    );

  const yesterdayKey =
    new Intl.DateTimeFormat(
      'en-CA',
      {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }
    ).format(yesterday);

  const time =
    date.toLocaleTimeString(
      'es-CO',
      {
        timeZone,
        hour: 'numeric',
        minute: '2-digit'
      }
    );

  if (dateKey === todayKey) {
    return `Hoy · ${time}`;
  }

  if (dateKey === yesterdayKey) {
    return `Ayer · ${time}`;
  }

  return date.toLocaleString(
    'es-CO',
    {
      timeZone,
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    }
  );
}


function auditPeriodStart(period) {
  const now = new Date();

  if (period === 'day') {
    return new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate()
    );
  }

  if (period === 'week') {
    const result = new Date(now);

    const day =
      result.getDay() || 7;

    result.setDate(
      result.getDate()
      - day
      + 1
    );

    result.setHours(
      0,
      0,
      0,
      0
    );

    return result;
  }

  if (period === 'month') {
    return new Date(
      now.getFullYear(),
      now.getMonth(),
      1
    );
  }

  if (period === 'year') {
    return new Date(
      now.getFullYear(),
      0,
      1
    );
  }

  return null;
}


function filteredAuditLogs() {
  const search =
    document
      .querySelector('#audit-search')
      ?.value
      .trim()
      .toLowerCase()
    || '';

  const category =
    document
      .querySelector('#audit-category')
      ?.value
    || 'all';

  const actor =
    document
      .querySelector('#audit-user')
      ?.value
    || 'all';

  const period =
    document
      .querySelector('#audit-period')
      ?.value
    || 'all';

  const start =
    auditPeriodStart(period);

  return systemAuditLogs.filter(
    log => {
      const haystack = [
        log.actor_name,
        log.actor_role,
        log.action,
        log.entity_type,
        log.entity_name,
        log.description
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      const matchesSearch =
        !search
        || haystack.includes(search);

      const matchesCategory =
        category === 'all'
        || auditActionCategory(
          log.action
        ) === category;

      const matchesActor =
        actor === 'all'
        || String(
          log.actor_user_id
        ) === actor;

      const matchesPeriod =
        !start
        || (
          log.created_at
          && new Date(
            log.created_at
          ) >= start
        );

      return (
        matchesSearch
        && matchesCategory
        && matchesActor
        && matchesPeriod
      );
    }
  );
}


function renderAuditTimeline() {
  const container =
    document.querySelector(
      '#audit-timeline'
    );

  if (!container) {
    console.warn(
      'No existe #audit-timeline'
    );

    return;
  }

  const logs =
    filteredAuditLogs();

  const counter =
    document.querySelector(
      '#audit-visible-count'
    );

  if (counter) {
    counter.textContent =
      String(logs.length);
  }

  if (!logs.length) {
    container.innerHTML = `
      <div class="empty audit-empty">
        No hay movimientos para
        los filtros seleccionados.
      </div>
    `;

    return;
  }

  const html =
    logs.map(log => {

      const category =
        auditActionCategory(
          log.action
        );

      const entity =
        auditEntityLabel(log);

      const description =
        log.description || '';

      return `
        <article
          class="audit-event"
          data-audit-id="${log.id}"
        >

          <div
            class="
              audit-event-icon
              audit-event-${category}
            "
          >
            ${auditActionIcon(
        log.action
      )}
          </div>


          <div
            class="audit-event-body"
          >

            <div
              class="audit-event-main"
            >

              <div
                class="audit-event-title"
              >

                <div
                  class="audit-event-title-row"
                >

                  <span
                    class="
                      audit-type-badge
                      audit-type-${category}
                    "
                  >
                    ${auditCategoryLabel(
        log.action
      )}
                  </span>


                  <strong>
                    ${log.actor_name || 'Sistema'}
                  </strong>


                  <span>
                    ${auditActionLabel(
        log.action
      )}
                  </span>

                </div>


                <b
                  class="audit-entity-name"
                >
                  ${entity}
                </b>

              </div>


              <time>
                ${auditDate(
        log.created_at
      )}
              </time>

            </div>


            <div
              class="audit-event-meta"
            >

              <span
                class="pill"
              >
                ${auditRoleLabel(
        log.actor_role
      )}
              </span>


              ${description
          ? `
                    <span
                      class="audit-short-description"
                    >
                      ${description}
                    </span>
                  `
          : ''
        }


              <button
                type="button"
                class="audit-detail-toggle"
                data-audit-toggle="${log.id}"
              >
                Ver detalle
              </button>

            </div>


            <div
              class="audit-event-detail"
              id="audit-detail-${log.id}"
              hidden
            >

              <div
                class="audit-detail-grid"
              >

                <div>
                  <small>Acción</small>

                  <strong>
                    ${log.action || '—'}
                  </strong>
                </div>


                <div>
                  <small>Tipo</small>

                  <strong>
                    ${log.entity_type || '—'}
                  </strong>
                </div>


                <div>
                  <small>ID</small>

                  <strong>
                    ${log.entity_id || '—'}
                  </strong>
                </div>


                <div>
                  <small>Usuario</small>

                  <strong>
                    ${log.actor_name || 'Sistema'}
                  </strong>
                </div>

              </div>


              ${description
          ? `
                    <div
                      class="audit-detail-description"
                    >
                      <small>
                        Descripción
                      </small>

                      <p>
                        ${description}
                      </p>
                    </div>
                  `
          : ''
        }

            </div>

          </div>

        </article>
      `;
    }).join('');

  container.innerHTML =
    html;

  bindAuditDetailToggles();
}


function bindAuditDetailToggles() {
  document
    .querySelectorAll(
      '[data-audit-toggle]'
    )
    .forEach(
      button => {

        button.onclick = () => {

          const id =
            button.dataset.auditToggle;

          const detail =
            document.getElementById(
              `audit-detail-${id}`
            );

          if (!detail) {
            return;
          }

          const opening =
            detail.hidden;

          detail.hidden =
            !opening;

          button.textContent =
            opening
              ? 'Ocultar detalle'
              : 'Ver detalle';
        };

      }
    );
}


async function loadSystemAudit() {
  const response =
    await authenticatedFetch(
      `${API_BASE}/api/audit?limit=500`
    );

  const data =
    await response
      .json()
      .catch(
        () => []
      );

  if (!response.ok) {
    throw new Error(
      data.detail
      || 'No fue posible cargar la auditoría.'
    );
  }

  systemAuditLogs =
    Array.isArray(data)
      ? data
      : [];

  systemAuditLoaded = true;
}


function auditView() {
  const actors = [
    ...new Map(
      systemAuditLogs
        .filter(
          log =>
            log.actor_user_id
        )
        .map(
          log => [
            String(
              log.actor_user_id
            ),
            log.actor_name
          ]
        )
    ).entries()
  ];

  return `
    <section
      class="audit-page"
    >

      <div
        class="audit-summary-grid"
      >

        <article
          class="card audit-summary-card"
        >
          <span>
            Movimientos
          </span>

          <strong>
            ${systemAuditLogs.length}
          </strong>
        </article>


        <article
          class="card audit-summary-card"
        >
          <span>
            Usuarios
          </span>

          <strong>
            ${actors.length}
          </strong>
        </article>


        <article
          class="card audit-summary-card"
        >
          <span>
            Mostrando
          </span>

          <strong
            id="audit-visible-count"
          >
            ${systemAuditLogs.length}
          </strong>
        </article>

      </div>


      <section
        class="card audit-card"
      >

        <div
          class="card-head"
        >

          <div>
            <p class="eyebrow">
              CONTROL INTERNO
            </p>

            <h2>
              Historial del sistema
            </h2>

            <p
              class="audit-subtitle"
            >
              Consulta quién realizó cada
              operación dentro de
              La Patrona VIP.
            </p>
          </div>


          <button
            type="button"
            class="btn secondary"
            id="audit-refresh"
          >
            Actualizar
          </button>

        </div>


        <div
          class="audit-toolbar"
        >

          <input
            class="input"
            id="audit-search"
            type="search"
            placeholder="Buscar usuario, producto, venta..."
            autocomplete="off"
          />


          <select
            class="input"
            id="audit-category"
          >
            <option value="all">
              Todas las acciones
            </option>

            <option value="sales">
              Ventas
            </option>

            <option value="cash">
              Caja
            </option>

            <option value="inventory">
              Inventario y QR
            </option>

            <option value="expenses">
              Gastos
            </option>

            <option value="users">
              Usuarios
            </option>
          </select>


          <select
            class="input"
            id="audit-user"
          >
            <option value="all">
              Todos los usuarios
            </option>

            ${actors
      .map(
        ([id, name]) => `
                    <option
                      value="${id}"
                    >
                      ${name}
                    </option>
                  `
      )
      .join('')
    }
          </select>


          <select
            class="input"
            id="audit-period"
          >
            <option value="all">
              Todo el historial
            </option>

            <option value="day">
              Hoy
            </option>

            <option value="week">
              Esta semana
            </option>

            <option value="month">
              Este mes
            </option>

            <option value="year">
              Este año
            </option>
          </select>

        </div>


        <div
          class="audit-timeline"
          id="audit-timeline"
        >
        </div>

      </section>

    </section>
  `;
}


async function openAuditModule() {
  try {
    currentView = 'audit';

    sessionStorage.setItem(
      'lp-current-view',
      currentView
    );

    await loadSystemAudit();

    render('audit');

    // La vista ya existe en el DOM.
    // Ahora conectamos filtros y pintamos timeline.
    bindAuditEvents();
    renderAuditTimeline();

  } catch (error) {
    console.error(
      'Error cargando Auditoría:',
      error
    );

    alert(
      error.message
      || 'No fue posible abrir Auditoría.'
    );
  }
}


function bindAuditEvents() {
  [
    '#audit-search',
    '#audit-category',
    '#audit-user',
    '#audit-period'
  ].forEach(
    selector => {
      const element =
        document.querySelector(
          selector
        );

      if (!element) {
        return;
      }

      element.addEventListener(
        selector === '#audit-search'
          ? 'input'
          : 'change',
        renderAuditTimeline
      );
    }
  );

  document
    .querySelector(
      '#audit-refresh'
    )
    ?.addEventListener(
      'click',
      async () => {
        try {
          await loadSystemAudit();

          render('audit');

          bindAuditEvents();
          renderAuditTimeline();

        } catch (error) {
          alert(
            error.message
            || 'No fue posible actualizar.'
          );
        }
      }
    );

  document
    .querySelectorAll(
      '[data-audit-toggle]'
    )
    .forEach(
      button => {

        button.addEventListener(
          'click',
          () => {

            const id =
              button.dataset.auditToggle;

            const detail =
              document.getElementById(
                `audit-detail-${id}`
              );

            if (!detail) {
              return;
            }

            const opening =
              detail.hidden;

            detail.hidden =
              !opening;

            button.textContent =
              opening
                ? 'Ocultar detalle'
                : 'Ver detalle';
          }
        );

      }
    );

  renderAuditTimeline();
}


function ensureAuditNavItem() {
  // El botón Auditoría ya existe en index.html.
  // Su visibilidad la controla allowedViewsForRole().
  return;
}



function allowedViewsForRole(
  role
) {
  switch (role) {

    case 'ADMIN':
      return [
        'dashboard',
        'sales',
        'inventory',
        'expenses',
        'purchases',
        'users',
        'audit'
      ];

    case 'VENDEDOR':
      return [
        'dashboard',
        'sales',
        'inventory'
      ];

    default:
      return [
        'dashboard'
      ];
  }
}


function applyRoleNavigation() {
  const user =
    state.currentUser;

  if (!user) {
    return;
  }

  const allowed =
    allowedViewsForRole(
      user.role
    );

  document
    .querySelectorAll(
      '#nav [data-view]'
    )
    .forEach(
      button => {

        const permitted =
          allowed.includes(
            button.dataset.view
          );

        button.hidden =
          !permitted;
      }
    );

  // Also apply to drawer
  document
    .querySelectorAll(
      '#drawer-nav [data-view], #drawer-nav-admin [data-view]'
    )
    .forEach(
      item => {
        item.hidden =
          !allowed.includes(
            item.dataset.view
          );
      }
    );

  // Hide admin section header if no admin items visible
  const adminSection = document.getElementById('drawer-admin-section');
  const adminNav = document.getElementById('drawer-nav-admin');
  if (adminSection && adminNav) {
    const hasVisible = adminNav.querySelector('.drawer-item[data-view]:not([hidden])');
    adminSection.style.display = hasVisible ? '' : 'none';
    adminNav.style.display = hasVisible ? '' : 'none';
  }


  if (
    !allowed.includes(
      currentView
    )
  ) {
    currentView =
      allowed[0] ||
      'dashboard';

    sessionStorage.setItem(
      'lp-current-view',
      currentView
    );
  }
}



function applyRoleActionPermissions() {
  const role =
    state.currentUser?.role;

  if (!role) {
    return;
  }

  const isAdmin =
    role === 'ADMIN';

  const canAdjustInventory =
    role === 'ADMIN';


  // ----------------------------------------
  // PRODUCTOS / QR
  // ----------------------------------------

  [
    '#new-product',
    '#admin-generate-qr',
    '#admin-delete-product',
    '#admin-clear-session'
  ].forEach(selector => {

    document
      .querySelector(selector)
      ?.toggleAttribute(
        'hidden',
        !isAdmin
      );

  });


  document
    .querySelectorAll(
      '.product-qr-btn,' +
      '.product-delete-qr-btn,' +
      '.product-delete-btn'
    )
    .forEach(element => {

      element.toggleAttribute(
        'hidden',
        !isAdmin
      );

    });


  // ----------------------------------------
  // MOVIMIENTOS DE INVENTARIO
  // ----------------------------------------

  document
    .querySelector(
      '#new-adjustment'
    )
    ?.toggleAttribute(
      'hidden',
      !canAdjustInventory
    );


  // ----------------------------------------
  // GASTOS
  // ----------------------------------------

  document
    .querySelector(
      '#new-expense'
    )
    ?.toggleAttribute(
      'hidden',
      !isAdmin
    );
}


function updateAuthenticatedUserUI() {
  const user =
    state.currentUser;

  if (!user) {
    return;
  }

  const name =
    document.querySelector(
      '#current-user-name'
    );

  const role =
    document.querySelector(
      '#current-user-role'
    );

  const avatar =
    document.querySelector(
      '#current-user-avatar'
    );

  if (name) {
    name.textContent =
      user.full_name ||
      user.username;
  }

  if (role) {
    role.textContent =
      getRoleLabel(
        user.role
      );
  }

  if (avatar) {
    avatar.textContent =
      getUserInitials(
        user.full_name ||
        user.username
      );
  }

  // Update mobile dropdown
  const mName = document.getElementById('mobile-user-name');
  const mRole = document.getElementById('mobile-user-role');
  const mAvatar = document.getElementById('mobile-user-avatar');
  if (mName) mName.textContent = user.full_name || user.username;
  if (mRole) mRole.textContent = getRoleLabel(user.role);
  if (mAvatar) mAvatar.textContent = getUserInitials(user.full_name || user.username);

  applyRoleNavigation();
}


function showLoginScreen() {

  // Nunca mostrar el login durante un render interno
  // si la sesión continúa autenticada.
  if (state.currentUser) {
    hideLoginScreen();
    return;
  }

  document.body.classList.add(
    'auth-locked'
  );

  document
    .querySelector(
      '#login-screen'
    )
    ?.classList.remove(
      'is-hidden'
    );

  const password =
    document.querySelector(
      '#login-password'
    );

  if (password) {
    password.value = '';
  }
}


function hideLoginScreen() {
  document.body.classList.remove(
    'auth-locked'
  );

  document
    .querySelector(
      '#login-screen'
    )
    ?.classList.add(
      'is-hidden'
    );
}


async function loginUser(
  username,
  password
) {
  const response =
    await fetch(
      `${API_BASE}/api/auth/login`,
      {
        method: 'POST',

        credentials:
          'include',

        headers: {
          'Content-Type':
            'application/json'
        },

        body:
          JSON.stringify({
            username,
            password
          })
      }
    );


  const data =
    await response
      .json()
      .catch(
        () => ({})
      );


  if (!response.ok) {
    throw new Error(
      data.detail ||
      'No fue posible iniciar sesión.'
    );
  }


  state.currentUser =
    data.user;


  localStorage.setItem(
    AUTH_USER_KEY,
    JSON.stringify(
      data.user
    )
  );


  // Eliminamos cualquier JWT viejo
  // que hubiese quedado guardado.
  localStorage.removeItem(
    AUTH_TOKEN_KEY
  );


  hideLoginScreen();

  updateAuthenticatedUserUI();


  currentView =
    allowedViewsForRole(
      data.user.role
    )[0] ||
    'dashboard';


  sessionStorage.setItem(
    'lp-current-view',
    currentView
  );


  await syncFromApi(
    false
  );


  render(
    currentView
  );
}



async function logoutUser(
  showMessage = true
) {
  try {
    await fetch(
      `${API_BASE}/api/auth/logout`,
      {
        method: 'POST',

        credentials:
          'include'
      }
    );

  } catch (error) {
    // La interfaz cerrará sesión
    // aunque el backend no responda.
  }


  localStorage.removeItem(
    AUTH_TOKEN_KEY
  );

  localStorage.removeItem(
    AUTH_USER_KEY
  );

  sessionStorage.removeItem(
    'lp-admin-key'
  );


  state.currentUser =
    null;


  currentView =
    'dashboard';


  sessionStorage.removeItem(
    'lp-current-view'
  );


  showLoginScreen();


  if (showMessage) {
    toast(
      'Sesión cerrada correctamente.'
    );
  }
}



async function restoreAuthSession() {
  try {

    const response =
      await fetch(
        `${API_BASE}/api/auth/me`,
        {
          credentials:
            'include'
        }
      );


    if (!response.ok) {
      throw new Error(
        'No hay sesión activa'
      );
    }


    const user =
      await response.json();


    state.currentUser =
      user;


    localStorage.setItem(
      AUTH_USER_KEY,
      JSON.stringify(
        user
      )
    );


    localStorage.removeItem(
      AUTH_TOKEN_KEY
    );


    hideLoginScreen();

    updateAuthenticatedUserUI();


    const allowed =
      allowedViewsForRole(
        user.role
      );


    if (
      !allowed.includes(
        currentView
      )
    ) {
      currentView =
        allowed[0] ||
        'dashboard';
    }


    await syncFromApi(
      false
    );


    render(
      currentView
    );


    return true;


  } catch (error) {

    localStorage.removeItem(
      AUTH_TOKEN_KEY
    );

    localStorage.removeItem(
      AUTH_USER_KEY
    );


    state.currentUser =
      null;


    showLoginScreen();


    return false;
  }
}



function initializeAuthentication() {
  const form =
    document.querySelector(
      '#login-form'
    );

  const logout =
    document.querySelector(
      '#logout-button'
    );


  form?.addEventListener(
    'submit',
    async event => {
      event.preventDefault();

      const username =
        document
          .querySelector(
            '#login-username'
          )
          ?.value
          .trim();

      const password =
        document
          .querySelector(
            '#login-password'
          )
          ?.value;

      const errorBox =
        document.querySelector(
          '#login-error'
        );

      const submit =
        document.querySelector(
          '#login-submit'
        );


      if (errorBox) {
        errorBox.hidden =
          true;
      }

      if (submit) {
        submit.disabled =
          true;

        submit.textContent =
          'Ingresando…';
      }


      try {
        await loginUser(
          username,
          password
        );

      } catch (error) {

        if (errorBox) {
          errorBox.textContent =
            error.message;

          errorBox.hidden =
            false;
        }

      } finally {

        if (submit) {
          submit.disabled =
            false;

          submit.textContent =
            'Iniciar sesión';
        }
      }
    }
  );


  logout?.addEventListener(
    'click',
    () => {
      logoutUser();
    }
  );


  // Theme toggle
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  const themeLabel = document.getElementById('theme-label');

  const savedTheme = localStorage.getItem('lp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeUI(savedTheme);

  themeToggle?.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('lp-theme', next);
    updateThemeUI(next);
  });

  function updateThemeUI(theme) {
    const icon = theme === 'dark' ? '\u2600' : '\u263E';
    const label = theme === 'dark' ? 'Claro' : 'Oscuro';
    if (themeIcon) themeIcon.textContent = icon;
    if (themeLabel) themeLabel.textContent = label;
    // Sync mobile theme buttons
    const mi = document.getElementById('mobile-theme-icon');
    const ml = document.getElementById('mobile-theme-label');
    const di = document.getElementById('drawer-theme-icon');
    const dl = document.getElementById('drawer-theme-label');
    if (mi) mi.textContent = icon;
    if (ml) ml.textContent = `Modo ${label.toLowerCase()}`;
    if (di) di.textContent = icon;
    if (dl) dl.textContent = `Modo ${label.toLowerCase()}`;
  }


  // ── Mobile drawer ──
  const hamburgerBtn = document.getElementById('hamburger-btn');
  const drawerOverlay = document.getElementById('drawer-overlay');
  const mobileDrawer = document.getElementById('mobile-drawer');
  const drawerCloseBtn = document.getElementById('drawer-close-btn');

  function openDrawer() {
    if (!mobileDrawer || !drawerOverlay) return;
    // Close notification panel if open
    if (typeof closeStockNotificationPanel === 'function') {
      closeStockNotificationPanel();
    }
    mobileDrawer.classList.add('open');
    drawerOverlay.classList.add('open');
    drawerOverlay.hidden = false;
    hamburgerBtn?.classList.add('open');
    hamburgerBtn?.setAttribute('aria-expanded', 'true');
    document.body.classList.add('menu-open');
    // Focus first item
    const first = mobileDrawer.querySelector('.drawer-item:not([hidden])');
    if (first) first.focus();
  }

  function closeDrawer() {
    if (!mobileDrawer || !drawerOverlay) return;
    mobileDrawer.classList.remove('open');
    drawerOverlay.classList.remove('open');
    drawerOverlay.hidden = true;
    hamburgerBtn?.classList.remove('open');
    hamburgerBtn?.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
    hamburgerBtn?.focus();
  }

  hamburgerBtn?.addEventListener('click', openDrawer);
  drawerCloseBtn?.addEventListener('click', closeDrawer);
  drawerOverlay?.addEventListener('click', closeDrawer);

  // Escape key closes drawer
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && mobileDrawer?.classList.contains('open')) {
      closeDrawer();
    }
  });

  // Drawer nav items
  document.querySelectorAll('#drawer-nav .drawer-item[data-view], #drawer-nav-admin .drawer-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;
      closeDrawer();
      if (view && views[view]) {
        render(view);
      }
    });
  });

  // Drawer theme toggle
  document.getElementById('drawer-theme-toggle')?.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('lp-theme', next);
    updateThemeUI(next);
  });

  // Drawer logout
  document.getElementById('drawer-logout-button')?.addEventListener('click', () => {
    closeDrawer();
    logoutUser();
  });


  // ── Mobile user dropdown ──
  const topbarUser = document.querySelector('.topbar-user');
  const mobileDropdown = document.getElementById('mobile-user-dropdown');

  topbarUser?.addEventListener('click', e => {
    if (window.innerWidth > 600) return;
    e.stopPropagation();
    // Close notification panel if open
    if (typeof closeStockNotificationPanel === 'function') {
      closeStockNotificationPanel();
    }
    if (mobileDropdown) mobileDropdown.hidden = !mobileDropdown.hidden;
  });

  document.addEventListener('click', e => {
    if (mobileDropdown && !mobileDropdown.contains(e.target)) {
      mobileDropdown.hidden = true;
    }
  });

  document.getElementById('mobile-theme-toggle')?.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('lp-theme', next);
    updateThemeUI(next);
    if (mobileDropdown) mobileDropdown.hidden = true;
  });

  document.getElementById('mobile-logout-button')?.addEventListener('click', () => {
    if (mobileDropdown) mobileDropdown.hidden = true;
    logoutUser();
  });


  restoreAuthSession();
}



function closeQrModal() {
  document
    .querySelector('#qr-modal')
    ?.remove();
}


function showQrModal(qr) {
  closeQrModal();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="qr-modal"
      >
        <div class="modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">
                CONTROL DE PRODUCTO
              </p>

              <h2>
                Código QR
              </h2>
            </div>

            <button
              type="button"
              class="icon-btn"
              id="close-qr-modal"
            >
              ×
            </button>
          </div>

          <div
            style="
              text-align:center;
              padding:24px 8px;
            "
          >
            <h3>
              ${qr.product_name}
            </h3>

            <p
              style="
                opacity:.7;
                margin-bottom:18px;
              "
            >
              ${qr.sku || 'Sin SKU'}
            </p>

            <div
              style="
                background:#fff;
                display:inline-block;
                padding:18px;
                border-radius:18px;
              "
            >
              <img
                src="${qr.image_data_url}"
                alt="QR ${qr.product_name}"
                style="
                  width:240px;
                  max-width:70vw;
                  display:block;
                "
              />
            </div>

            <p
              style="
                margin-top:18px;
                font-family:monospace;
                word-break:break-all;
              "
            >
              ${qr.code}
            </p>

            <div
              style="
                display:flex;
                gap:10px;
                justify-content:center;
                flex-wrap:wrap;
                margin-top:20px;
              "
            >
              <button
                type="button"
                class="btn primary"
                id="print-product-qr"
              >
                Imprimir QR
              </button>

              <a
                class="btn secondary"
                href="${qr.image_data_url}"
                download="QR-${qr.product_id}.png"
              >
                Descargar PNG
              </a>
            </div>
          </div>
        </div>
      </div>
    `
  );

  document
    .querySelector('#close-qr-modal')
    ?.addEventListener(
      'click',
      closeQrModal
    );

  document
    .querySelector('#qr-modal')
    ?.addEventListener(
      'click',
      event => {
        if (
          event.target.id === 'qr-modal'
        ) {
          closeQrModal();
        }
      }
    );

  document
    .querySelector('#print-product-qr')
    ?.addEventListener(
      'click',
      () => {
        const printWindow =
          window.open('', '_blank');

        if (!printWindow) {
          toast(
            'El navegador bloqueó la ventana de impresión.'
          );

          return;
        }

        printWindow.document.write(`
          <!doctype html>
          <html lang="es">
          <head>
            <meta charset="UTF-8">
            <title>
              QR ${qr.product_name}
            </title>

            <style>
              body {
                margin: 0;
                font-family: Arial, sans-serif;
                text-align: center;
              }

              .label {
                width: 70mm;
                min-height: 90mm;
                margin: 0 auto;
                padding: 8mm;
                box-sizing: border-box;
              }

              img {
                width: 48mm;
                height: 48mm;
              }

              h2 {
                margin: 4mm 0 1mm;
                font-size: 16px;
              }

              p {
                margin: 1mm 0;
                font-size: 10px;
              }

              .code {
                font-family: monospace;
                word-break: break-all;
              }
            </style>
          </head>

          <body>
            <div class="label">
              <strong>
                LA PATRONA VIP
              </strong>

              <h2>
                ${qr.product_name}
              </h2>

              <img
                src="${qr.image_data_url}"
              />

              <p>
                ${qr.sku || 'Sin SKU'}
              </p>

              <p class="code">
                ${qr.code}
              </p>
            </div>

            <script>
              window.onload = () => {
                window.print();
              };
            <\/script>
          </body>
          </html>
        `);

        printWindow.document.close();
      }
    );
}




async function generateProductQr(productId) {
  productId = Number(productId);

  currentView = 'inventory';

  if (!productId) {
    toast(
      'Producto inválido.'
    );

    return;
  }

  try {
    const response = await adminFetch(
      `${API_BASE}/api/products/${productId}/qr`,
      {
        method: 'POST'
      }
    );

    if (!response.ok) {
      const error = await response.json()
        .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible obtener el QR.'
      );
    }

    const qr = await response.json();

    // Actualizamos productos para refrescar has_qr.
    await syncFromApi(false);

    // Volvemos explícitamente a Inventario.
    render('inventory');

    // Abrimos el QR después del render.
    showQrModal(qr);

    toast(
      qr.created
        ? 'QR generado correctamente.'
        : 'QR cargado correctamente.'
    );

  } catch (error) {
    currentView = 'inventory';

    toast(
      error.message
    );
  }
}


async function deleteProductQr(productId) {
  productId = Number(productId);

  currentView = 'inventory';

  const product = state.products.find(
    item =>
      Number(item.id) === productId
  );

  if (!product) {
    toast(
      'Producto no encontrado.'
    );

    return;
  }

  const confirmed = window.confirm(
    `¿Eliminar el código QR de "${product.name}"?\n\n` +
    'El producto, stock, ventas e historial se conservarán.'
  );

  if (!confirmed) {
    return;
  }

  try {
    const response = await adminFetch(
      `${API_BASE}/api/products/${productId}/qr`,
      {
        method: 'DELETE'
      }
    );

    if (!response.ok) {
      const error = await response.json()
        .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible eliminar el QR.'
      );
    }

    // Refresca state.products y has_qr.
    await syncFromApi(false);

    // Mantiene la vista en Inventario.
    render('inventory');

    toast(
      `QR de ${product.name} eliminado correctamente.`
    );

  } catch (error) {
    currentView = 'inventory';

    toast(
      error.message
    );
  }
}


async function deleteProductById(productId) {
  productId = Number(productId);

  const product = state.products.find(
    item =>
      Number(item.id) === productId
  );

  if (!product) {
    toast(
      'Producto no encontrado.'
    );

    return;
  }

  const confirmed = window.confirm(
    `¿Eliminar "${product.name}"?\n\n` +
    'Las ventas y movimientos históricos ' +
    'se conservarán.'
  );

  if (!confirmed) {
    return;
  }

  try {
    const response = await adminFetch(
      `${API_BASE}/api/products/${productId}`,
      {
        method: 'DELETE'
      }
    );

    if (!response.ok) {
      const error = await response.json()
        .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible eliminar el producto.'
      );
    }

    await syncFromApi(false);

    render('inventory');

    toast(
      `${product.name} eliminado del inventario.`
    );

  } catch (error) {
    toast(error.message);
  }
}

/* ============================================================
   QR SCANNER
============================================================ */

let qrScannerInstance = null;
let qrScanningActive = false;

function openQrScanner() {
  document.querySelector('#qr-scanner-overlay')?.remove();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="qr-scanner-overlay" id="qr-scanner-overlay">
        <div class="qr-scanner-header">
          <button type="button" class="btn secondary" id="qr-scanner-close">
            Cerrar
          </button>
          <span class="eyebrow" style="color:var(--gold-light);">ESCANEAR CÓDIGO QR</span>
        </div>
        <div id="qr-scanner-viewport" class="qr-scanner-viewport"></div>
        <div class="qr-scanner-footer">
          <p id="qr-scanner-status" class="qr-scanner-status">
            Solicitando acceso a la cámara...
          </p>
        </div>
      </div>
    `
  );

  document.querySelector('#qr-scanner-close')
    ?.addEventListener('click', closeQrScanner);

  qrScanningActive = true;

  setTimeout(() => startQrCamera(), 100);
}

function startQrCamera() {
  if (typeof Html5Qrcode === 'undefined') {
    const statusEl = document.querySelector('#qr-scanner-status');
    if (statusEl) statusEl.textContent = 'Error: librería de escaneo no cargada.';
    return;
  }

  qrScannerInstance = new Html5Qrcode('qr-scanner-viewport');

  const config = {
    fps: 10,
    qrbox: { width: 250, height: 250 },
    aspectRatio: 1.0,
    formatsToSupport: undefined,
  };

  qrScannerInstance.start(
    { facingMode: 'environment' },
    config,
    decodedText => {
      if (!qrScanningActive) return;
      qrScanningActive = false;
      handleQrScanResult(decodedText);
    },
    () => {}
  ).catch(err => {
    const statusEl = document.querySelector('#qr-scanner-status');
    if (statusEl) {
      if (err?.toString?.().includes('NotAllowedError') || err?.toString?.().includes('Permission')) {
        statusEl.textContent = 'Debes permitir el acceso a la cámara para escanear códigos QR.';
      } else {
        statusEl.textContent = 'No fue posible acceder a la cámara. Verifica los permisos del navegador.';
      }
    }
    qrScanningActive = false;
  });
}

function closeQrScanner() {
  qrScanningActive = false;

  if (qrScannerInstance) {
    try {
      qrScannerInstance.stop().catch(() => {});
      qrScannerInstance.clear();
    } catch { }
    qrScannerInstance = null;
  }

  document.querySelector('#qr-scanner-overlay')?.remove();
}

async function handleQrScanResult(qrValue) {
  closeQrScanner();

  const loadingOverlay = document.body;
  loadingOverlay.insertAdjacentHTML(
    'beforeend',
    `
      <div class="qr-scanner-overlay" id="qr-resolving-overlay" style="z-index:10001;">
        <div class="qr-scanner-footer" style="margin-top:auto;">
          <p class="qr-scanner-status" style="color:var(--gold-light);">
            Validando código QR...
          </p>
        </div>
      </div>
    `
  );

  try {
    const response = await authenticatedFetch(
      `${API_BASE}/api/qr/resolve`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ qr_value: qrValue }),
      }
    );

    document.querySelector('#qr-resolving-overlay')?.remove();

    if (response.status === 404) {
      showQrInvalidModal(qrValue);
      return;
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      showQrInvalidModal(qrValue, error.detail);
      return;
    }

    const data = await response.json();
    showQrProductResultModal(data);

  } catch {
    document.querySelector('#qr-resolving-overlay')?.remove();
    showQrInvalidModal(qrValue);
  }
}

function showQrInvalidModal(qrValue, customMessage) {
  document.querySelector('#qr-invalid-modal')?.remove();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="qr-invalid-modal">
        <div class="modal qr-result-modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">CÓDIGO QR</p>
              <h2>Código QR no reconocido</h2>
            </div>
            <button type="button" class="icon-btn" id="close-qr-invalid-modal">×</button>
          </div>

          <div class="qr-result-body">
            <div class="qr-invalid-icon">✕</div>
            <p style="font-size:15px;margin-bottom:8px;">
              ${customMessage || 'Este código no corresponde a ningún producto registrado en el sistema.'}
            </p>
            <small style="color:var(--muted);word-break:break-all;font-family:monospace;">
              Valor leído: ${qrValue}
            </small>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn secondary" id="close-qr-invalid-btn">
              Cerrar
            </button>
            <button type="button" class="btn qr-scan-btn" id="rescan-qr-btn">
              Escanear nuevamente
            </button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-qr-invalid-modal')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-invalid-modal')?.remove();
    });

  document.querySelector('#close-qr-invalid-btn')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-invalid-modal')?.remove();
    });

  document.querySelector('#rescan-qr-btn')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-invalid-modal')?.remove();
      openQrScanner();
    });

  document.querySelector('#qr-invalid-modal')
    ?.addEventListener('click', e => {
      if (e.target.id === 'qr-invalid-modal') {
        e.target.remove();
      }
    });
}

function showQrProductResultModal(data) {
  document.querySelector('#qr-result-modal')?.remove();

  const product = data.product || {};
  const qr = data.qr || {};

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="qr-result-modal">
        <div class="modal qr-result-modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">PRODUCTO ENCONTRADO</p>
              <h2>${product.name || 'Producto'}</h2>
            </div>
            <button type="button" class="icon-btn" id="close-qr-result-modal">×</button>
          </div>

          <div class="qr-result-body">
            ${product.image_url
      ? `<img src="${product.image_url}" alt="${product.name}" class="qr-result-image" />`
      : `<div class="qr-result-image qr-result-image-placeholder">♪</div>`
    }

            <div class="qr-result-info">
              <div class="qr-result-row">
                <small>Nombre</small>
                <strong>${product.name || '—'}</strong>
              </div>
              <div class="qr-result-row">
                <small>SKU</small>
                <span>${product.sku || 'Sin SKU'}</span>
              </div>
              <div class="qr-result-row">
                <small>Precio</small>
                <strong>${money(product.price)}</strong>
              </div>
              <div class="qr-result-row">
                <small>Stock disponible</small>
                <span>${Number(product.stock || 0)} ${product.unit || 'unidades'}</span>
              </div>
              <div class="qr-result-row">
                <small>Código QR</small>
                <code>${qr.code || '—'}</code>
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn secondary" id="close-qr-result-btn">
              Cerrar
            </button>
            <button type="button" class="btn qr-scan-btn" id="rescan-qr-result-btn">
              Escanear otro
            </button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-qr-result-modal')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-result-modal')?.remove();
    });

  document.querySelector('#close-qr-result-btn')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-result-modal')?.remove();
    });

  document.querySelector('#rescan-qr-result-btn')
    ?.addEventListener('click', () => {
      document.querySelector('#qr-result-modal')?.remove();
      openQrScanner();
    });

  document.querySelector('#qr-result-modal')
    ?.addEventListener('click', e => {
      if (e.target.id === 'qr-result-modal') {
        e.target.remove();
      }
    });
}

async function generateSelectedProductQr() {
  const select =
    document.querySelector(
      '#admin-product-select'
    );

  if (!select) {
    toast(
      'No se encontró el selector de productos.'
    );

    return;
  }

  const productId =
    Number(select.value);

  if (!productId) {
    toast(
      'Selecciona un producto.'
    );

    return;
  }

  currentView = 'inventory';

  await generateProductQr(
    productId
  );
}


async function deleteSelectedProduct() {
  const select = document.querySelector(
    '#admin-product-select'
  );

  const productId = Number(
    select?.value
  );

  if (!productId) {
    toast(
      'Selecciona un producto.'
    );

    return;
  }

  const product = state.products.find(
    item =>
      Number(item.id) === productId
  );

  if (!product) {
    toast(
      'Producto no encontrado.'
    );

    return;
  }

  const confirmed = window.confirm(
    `¿Eliminar "${product.name}" del inventario?\n\n` +
    'Las ventas anteriores se conservarán.'
  );

  if (!confirmed) {
    return;
  }

  try {
    const response = await adminFetch(
      `${API_BASE}/api/products/${productId}`,
      {
        method: 'DELETE'
      }
    );

    if (!response.ok) {
      const error = await response.json()
        .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible eliminar el producto.'
      );
    }

    await syncFromApi(false);

    render('inventory');

    toast(
      `${product.name} fue eliminado del inventario.`
    );

  } catch (error) {
    toast(error.message);
  }
}




/* ============================================================
   DASHBOARD
============================================================ */

function dashboard() {
  const now = new Date();

  const localDateKey = dateValue => {
    if (!dateValue) {
      return '';
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
      return '';
    }

    return [
      date.getFullYear(),
      String(
        date.getMonth() + 1
      ).padStart(2, '0'),
      String(
        date.getDate()
      ).padStart(2, '0')
    ].join('-');
  };


  const startOfDay = date => {
    const result = new Date(date);

    result.setHours(
      0, 0, 0, 0
    );

    return result;
  };


  const endOfDay = date => {
    const result = new Date(date);

    result.setHours(
      23, 59, 59, 999
    );

    return result;
  };


  const getPeriodRange = period => {
    const end = endOfDay(now);
    let start = startOfDay(now);

    switch (period) {

      case 'week': {
        const day =
          now.getDay() || 7;

        start.setDate(
          start.getDate() - day + 1
        );

        break;
      }

      case 'month':
        start = new Date(
          now.getFullYear(),
          now.getMonth(),
          1
        );
        break;

      case 'year':
        start = new Date(
          now.getFullYear(),
          0,
          1
        );
        break;

      case 'day':
      default:
        break;
    }

    return {
      start,
      end
    };
  };


  const periodRange =
    getPeriodRange(
      dashboardPeriod
    );


  const isInsidePeriod = value => {
    if (!value) {
      return false;
    }

    const date =
      new Date(value);

    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return false;
    }

    return (
      date >= periodRange.start &&
      date <= periodRange.end
    );
  };


  const periodSales =
    state.sales.filter(
      sale =>
        isInsidePeriod(
          sale.created_at
        )
    );


  const periodExpenses =
    state.expenses.filter(
      expense =>
        isInsidePeriod(
          expense.created_at
        )
    );


  const salesTotal =
    periodSales.reduce(
      (total, sale) =>
        total +
        Number(
          sale.total || 0
        ),
      0
    );


  const expensesTotal =
    periodExpenses.reduce(
      (total, expense) =>
        total +
        Number(
          expense.value || 0
        ),
      0
    );


  const netMovement =
    salesTotal -
    expensesTotal;


  const averageTicket =
    periodSales.length
      ? salesTotal /
      periodSales.length
      : 0;


  const lowStockProducts =
    state.products.filter(
      product =>
        Number(
          product.stock
        ) <=
        Number(
          product.minimum_stock ?? 20
        )
    );


  const productsWithQr =
    state.products.filter(
      product =>
        product.has_qr
    ).length;


  const cashIsOpen =
    state.cashRegister?.status ===
    'OPEN' &&
    state.cashRegister?.session;


  const cashExpected =
    cashIsOpen
      ? Number(
        state.cashRegister
          .session
          .expected_amount || 0
      )
      : 0;


  const cashOpening =
    cashIsOpen
      ? Number(
        state.cashRegister
          .session
          .opening_amount || 0
      )
      : 0;


  const cashSales =
    cashIsOpen
      ? Number(
        state.cashRegister
          .session
          .cash_sales_total || 0
      )
      : 0;


  const cashExpenses =
    cashIsOpen
      ? Number(
        state.cashRegister
          .session
          .expenses_total || 0
      )
      : 0;


  const periodNames = {
    day: 'Hoy',
    week: 'Esta semana',
    month: 'Este mes',
    year: 'Este año'
  };


  // ==========================================================
  // DATOS DEL GRÁFICO
  // ==========================================================

  let chartData = [];


  if (dashboardPeriod === 'day') {

    const ranges = [
      [0, 4],
      [4, 8],
      [8, 12],
      [12, 16],
      [16, 20],
      [20, 24]
    ];

    chartData =
      ranges.map(
        ([from, to]) => {

          const total =
            periodSales
              .filter(
                sale => {
                  const hour =
                    new Date(
                      sale.created_at
                    ).getHours();

                  return (
                    hour >= from &&
                    hour < to
                  );
                }
              )
              .reduce(
                (sum, sale) =>
                  sum +
                  Number(
                    sale.total || 0
                  ),
                0
              );

          return {
            label:
              `${String(from).padStart(2, '0')}:00`,
            total
          };
        }
      );

  } else if (
    dashboardPeriod === 'week'
  ) {

    const formatter =
      new Intl.DateTimeFormat(
        'es-CO',
        {
          weekday: 'short'
        }
      );

    chartData =
      Array.from(
        { length: 7 },
        (_, index) => {

          const date =
            new Date(
              periodRange.start
            );

          date.setDate(
            date.getDate() +
            index
          );

          const key =
            localDateKey(date);

          const total =
            periodSales
              .filter(
                sale =>
                  localDateKey(
                    sale.created_at
                  ) === key
              )
              .reduce(
                (sum, sale) =>
                  sum +
                  Number(
                    sale.total || 0
                  ),
                0
              );

          return {
            label:
              formatter
                .format(date)
                .replace('.', ''),
            total
          };
        }
      );

  } else if (
    dashboardPeriod === 'month'
  ) {

    const weeks = [
      [1, 7],
      [8, 14],
      [15, 21],
      [22, 31]
    ];

    chartData =
      weeks.map(
        ([from, to], index) => {

          const total =
            periodSales
              .filter(
                sale => {
                  const date =
                    new Date(
                      sale.created_at
                    );

                  const day =
                    date.getDate();

                  return (
                    day >= from &&
                    day <= to
                  );
                }
              )
              .reduce(
                (sum, sale) =>
                  sum +
                  Number(
                    sale.total || 0
                  ),
                0
              );

          return {
            label:
              `Sem ${index + 1}`,
            total
          };
        }
      );

  } else {

    const monthNames = [
      'Ene',
      'Feb',
      'Mar',
      'Abr',
      'May',
      'Jun',
      'Jul',
      'Ago',
      'Sep',
      'Oct',
      'Nov',
      'Dic'
    ];

    chartData =
      monthNames.map(
        (label, month) => {

          const total =
            periodSales
              .filter(
                sale =>
                  new Date(
                    sale.created_at
                  ).getMonth() === month
              )
              .reduce(
                (sum, sale) =>
                  sum +
                  Number(
                    sale.total || 0
                  ),
                0
              );

          return {
            label,
            total
          };
        }
      );
  }


  const maxChartValue =
    Math.max(
      ...chartData.map(
        item =>
          item.total
      ),
      1
    );


  const recentSales =
    [...periodSales]
      .sort(
        (a, b) =>
          new Date(
            b.created_at || 0
          ) -
          new Date(
            a.created_at || 0
          )
      )
      .slice(0, 5);


  return `
    <div class="dashboard-welcome">

      <div>
        <p class="eyebrow">
          OPERACIÓN EN TIEMPO REAL
        </p>

        <h2>
          Estado general del negocio
        </h2>

        <p>
          Analiza ventas y gastos por
          día, semana, mes o año.
        </p>
      </div>


      <div class="dashboard-controls">

        <select
          id="dashboard-period"
          class="input dashboard-period-select"
        >
          <option
            value="day"
            ${dashboardPeriod === 'day'
      ? 'selected'
      : ''
    }
          >
            Día
          </option>

          <option
            value="week"
            ${dashboardPeriod === 'week'
      ? 'selected'
      : ''
    }
          >
            Semana
          </option>

          <option
            value="month"
            ${dashboardPeriod === 'month'
      ? 'selected'
      : ''
    }
          >
            Mes
          </option>

          <option
            value="year"
            ${dashboardPeriod === 'year'
      ? 'selected'
      : ''
    }
          >
            Año
          </option>
        </select>


        <span
          class="pill ${cashIsOpen
      ? 'green'
      : 'yellow'
    }"
        >
          ${cashIsOpen
      ? 'Caja abierta'
      : 'Caja cerrada'
    }
        </span>

      </div>

    </div>


    <div class="dashboard-period-heading">

      <span>
        ${periodNames[
    dashboardPeriod
    ]
    }
      </span>

      <small>
        ${periodRange.start
      .toLocaleDateString(
        'es-CO'
      )
    }
        ${dashboardPeriod !== 'day'
      ? ` → ${periodRange.end
        .toLocaleDateString(
          'es-CO'
        )
      }`
      : ''
    }
      </small>

    </div>


    <div class="grid metrics dashboard-metrics">

      <div class="card metric">

        <span class="label">
          Ventas
        </span>

        <div class="value">
          ${money(salesTotal)}
        </div>

        <span class="delta positive">
          ${periodSales.length}
          ${periodSales.length === 1
      ? 'venta'
      : 'ventas'
    }
        </span>

      </div>


      <div class="card metric">

        <span class="label">
          Gastos
        </span>

        <div class="value">
          ${money(expensesTotal)}
        </div>

        <span class="delta negative">
          ${periodExpenses.length}
          ${periodExpenses.length === 1
      ? 'egreso'
      : 'egresos'
    }
        </span>

      </div>


      <div class="card metric">

        <span class="label">
          Movimiento neto
        </span>

        <div class="value">
          ${money(netMovement)}
        </div>

        <span
          class="delta ${netMovement >= 0
      ? 'positive'
      : 'negative'
    }"
        >
          Ventas menos gastos
        </span>

      </div>


      <div class="card metric">

        <span class="label">
          Ticket promedio
        </span>

        <div class="value">
          ${money(averageTicket)}
        </div>

        <span class="delta positive">
          Promedio por venta
        </span>

      </div>

    </div>

    ${(() => {
      const histByMonth = {};
      (state.inventoryHistory || []).forEach(h => {
        const d = h.period_date ? h.period_date.slice(0, 7) : '';
        if (!d) return;
        if (!histByMonth[d]) histByMonth[d] = { total: 0, items: 0 };
        histByMonth[d].total += Number(h.total_sold || 0);
        histByMonth[d].items += Number(h.units_sold || 0);
      });
      const months = Object.keys(histByMonth).sort();
      if (!months.length) return '';
      const grandTotal = months.reduce((s, m) => s + histByMonth[m].total, 0);
      const monthNames = { '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic' };
      return `
        <section class="card historical-sales-card">
          <div class="card-head">
            <div>
              <h2>Ventas históricas (inventario)</h2>
              <small class="text-muted">Datos importados · ${months.length} períodos · ${money(grandTotal)} total</small>
            </div>
          </div>
          <div class="historical-sales-grid">
            ${months.map(m => {
              const [yr, mo] = m.split('-');
              const label = (monthNames[mo] || mo) + ' ' + yr;
              const val = histByMonth[m].total;
              return '<div class="historical-sales-item">' +
                '<span class="historical-sales-label">' + label + '</span>' +
                '<span class="historical-sales-value">' + money(val) + '</span>' +
                '<span class="historical-sales-units">' + histByMonth[m].items + ' uds</span>' +
                '</div>';
            }).join('')}
          </div>
        </section>`;
    })()}


    <div class="grid dashboard-main-grid">

      <section class="card dashboard-sales-chart">

        <div class="card-head">

          <div>
            <h2>
              Ventas · ${periodNames[
    dashboardPeriod
    ]
    }
            </h2>

            <small>
              Distribución del período
            </small>
          </div>

          <span
            class="link"
            data-view="sales"
          >
            Ver ventas →
          </span>

        </div>


        <div
          class="
            dashboard-chart
            dashboard-chart-${dashboardPeriod}
          "
        >

          ${chartData.map(
      item => {

        const percentage =
          item.total > 0
            ? Math.max(
              7,
              (
                item.total /
                maxChartValue
              ) * 100
            )
            : 2;

        return `
                  <div class="dashboard-bar-item">

                    <div
                      class="dashboard-bar-value"
                      title="${money(
          item.total
        )}"
                    >
                      ${item.total
            ? money(
              item.total
            )
            : '—'
          }
                    </div>

                    <div
                      class="dashboard-bar-track"
                    >
                      <div
                        class="dashboard-bar-fill"
                        style="
                          height: ${percentage}%;
                          --bar-pct: ${percentage}%;
                        "
                      ></div>
                    </div>

                    <span>
                      ${item.label}
                    </span>

                  </div>
                `;
      }
    ).join('')
    }

        </div>

      </section>


      <section class="card dashboard-cash">

        <div class="card-head">

          <div>
            <h2>
              Caja actual
            </h2>

            <small>
              Estado en tiempo real
            </small>
          </div>

          <span
            class="pill ${cashIsOpen
      ? 'green'
      : 'yellow'
    }"
          >
            ${cashIsOpen
      ? 'Abierta'
      : 'Cerrada'
    }
          </span>

        </div>


        ${cashIsOpen
      ? `
              <div
                class="
                  dashboard-summary-list
                "
              >

                <div>
                  <span>
                    Base inicial
                  </span>

                  <strong>
                    ${money(
        cashOpening
      )}
                  </strong>
                </div>

                <div>
                  <span>
                    Ventas efectivo
                  </span>

                  <strong>
                    + ${money(
        cashSales
      )}
                  </strong>
                </div>

                <div>
                  <span>
                    Gastos efectivo
                  </span>

                  <strong
                    class="negative"
                  >
                    - ${money(
        cashExpenses
      )}
                  </strong>
                </div>

                <div
                  class="
                    dashboard-summary-total
                  "
                >
                  <span>
                    Esperado
                  </span>

                  <strong>
                    ${money(
        cashExpected
      )}
                  </strong>
                </div>

              </div>
            `
      : `
              <div
                class="
                  dashboard-empty-state
                "
              >
                <strong>
                  No hay una caja abierta
                </strong>

                <p>
                  Abre una sesión desde
                  Ventas y caja.
                </p>

                <button
                  type="button"
                  class="btn"
                  data-view="sales"
                >
                  Ir a Ventas y caja
                </button>
              </div>
            `
    }

      </section>

    </div>


    <div class="grid dashboard-main-grid">

      <section class="card">

        <div class="card-head">

          <div>
            <h2>
              Ventas del período
            </h2>

            <small>
              Últimas operaciones
            </small>
          </div>

          <span
            class="pill"
          >
            ${periodSales.length}
          </span>

        </div>


        <div class="list">

          ${recentSales.length
      ? recentSales.map(
        sale => `
                    <div class="row">

                      <div>
                        <strong>
                          ${sale.id}
                        </strong>

                        <small>
                          ${sale.detail}
                        </small>
                      </div>

                      <div
                        class="
                          dashboard-row-right
                        "
                      >
                        <strong>
                          ${money(
          sale.total
        )}
                        </strong>

                        <small>
                          ${sale.payment}
                        </small>
                      </div>

                    </div>
                  `
      ).join('')
      : `
                  <div class="empty">
                    No hay ventas en este período.
                  </div>
                `
    }

        </div>

      </section>


      <section class="card">

        <div class="card-head">

          <div>
            <h2>
              Inventario crítico
            </h2>

            <small>
              Estado actual
            </small>
          </div>

          <span
            class="link"
            data-view="inventory"
          >
            Gestionar →
          </span>

        </div>


        <div class="list">

          ${lowStockProducts.length
      ? lowStockProducts
        .slice(0, 6)
        .map(
          product => `
                      <div class="row">

                        <div>
                          <strong>
                            ${product.name}
                          </strong>

                          <small>
                            ${Number(
            product.stock
          )}
                            ${product.unit}
                          </small>
                        </div>

                        <span
                          class="
                            pill yellow
                          "
                        >
                          Reponer
                        </span>

                      </div>
                    `
        ).join('')
      : `
                  <div
                    class="
                      dashboard-empty-state
                      compact
                    "
                  >
                    <strong>
                      Inventario saludable
                    </strong>

                    <p>
                      No hay productos
                      por debajo del mínimo.
                    </p>
                  </div>
                `
    }

        </div>

      </section>

    </div>


    <div class="grid dashboard-bottom-grid">

      <section class="card">

        <div class="card-head">

          <div>
            <h2>
              Control QR
            </h2>

            <small>
              Estado actual
            </small>
          </div>

          <span
            class="link"
            data-view="inventory"
          >
            Administrar →
          </span>

        </div>


        <div
          class="
            dashboard-qr-summary
          "
        >

          <div>
            <strong>
              ${productsWithQr}
            </strong>

            <span>
              Con QR
            </span>
          </div>

          <div>
            <strong>
              ${state.products.length -
    productsWithQr
    }
            </strong>

            <span>
              Sin QR
            </span>
          </div>

          <div>
            <strong>
              ${state.products.length
    }
            </strong>

            <span>
              Activos
            </span>
          </div>

        </div>

      </section>


      

    </div>
  `;
}


/* ============================================================
   SALES
============================================================ */


function saleDateTime(value) {

  if (!value) {
    return {
      date: '—',
      time: '—'
    };
  }

  let normalized =
    String(value);

  if (
    !normalized.endsWith('Z')
    && !/[+-]\d{2}:\d{2}$/.test(
      normalized
    )
  ) {
    normalized += 'Z';
  }

  const date =
    new Date(normalized);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return {
      date: '—',
      time: '—'
    };
  }

  return {
    date:
      new Intl.DateTimeFormat(
        'es-CO',
        {
          timeZone:
            'America/Bogota',
          day:
            '2-digit',
          month:
            '2-digit',
          year:
            'numeric'
        }
      ).format(date),

    time:
      new Intl.DateTimeFormat(
        'es-CO',
        {
          timeZone:
            'America/Bogota',
          hour:
            '2-digit',
          minute:
            '2-digit',
          hour12:
            true
        }
      ).format(date)
  };
}


function sales() {
  setTimeout(loadCashRegisterPanel, 0);
  setTimeout(setupSalesFilters, 0);

  return `
    <section class="card" style="margin-bottom:20px">
      <div class="card-head">
        <div>
          <p class="eyebrow">CAJA</p>
          <h2>Estado de caja</h2>
        </div>
      </div>

      <div id="cash-register-panel">
        <p style="color:var(--muted)">
          Consultando estado de caja...
        </p>
      </div>
    </section>

    <section
      class="card open-accounts-section"
      id="open-accounts-section"
      style="margin-bottom:20px"
    >
      <div class="card-head">
        <div>
          <p class="eyebrow">
            OPERACIÓN
          </p>

          <h2>
            Cuentas abiertas
          </h2>

          <small style="color:var(--muted)">
            Mesas, VIP y consumos pendientes de cobro
          </small>
        </div>

        <span class="pill">
          ${(state.openAccounts || [])
      .filter(
        account =>
          account.status === 'OPEN'
      )
      .length
    } abiertas
        </span>
      </div>

      <div class="open-accounts-grid">

        ${(state.openAccounts || [])
      .filter(
        account =>
          account.status === 'OPEN'
      )
      .length

      ? (state.openAccounts || [])
        .filter(
          account =>
            account.status === 'OPEN'
        )
        .map(
          account => `
                  <article class="open-account-card">

                    <div class="open-account-head">
                      <div>
                        <small>
                          ${account.account_type}
                        </small>

                        <strong>
                          ${account.label}
                        </strong>

                        ${account.zone
              ? `
                              <span>
                                ${account.zone}
                              </span>
                            `
              : ''
            }
                      </div>

                      <span class="pill green">
                        ABIERTA
                      </span>
                    </div>


                    <div class="open-account-summary">

                      <div>
                        <small>
                          Cuenta
                        </small>

                        <strong>
                          ${account.number}
                        </strong>
                      </div>

                      <div>
                        <small>
                          Responsable
                        </small>

                        <strong>
                          ${account.opened_by_name || '—'}
                        </strong>
                      </div>

                      <div>
                        <small>
                          Cliente
                        </small>

                        <strong>
                          ${account.customer_name || 'Consumidor final'}
                        </strong>
                      </div>

                      <div>
                        <small>
                          Total
                        </small>

                        <strong class="open-account-total">
                          ${money(account.total)}
                        </strong>
                      </div>

                    </div>


                    <div class="open-account-items-preview">

                      ${account.items?.length

              ? account.items
                .slice(-4)
                .map(
                  item => `
                                <div>
                                  <span>
                                    ${item.product_name}
                                  </span>

                                  <strong>
                                    × ${Number(item.quantity)}
                                  </strong>
                                </div>
                              `
                )
                .join('')

              : `
                            <div class="open-account-empty">
                              Sin consumos todavía.
                            </div>
                          `
            }

                    </div>


                    <div class="open-account-actions">

                      <button
                        type="button"
                        class="btn secondary open-account-add-item"
                        data-account-id="${account.id}"
                      >
                        + Agregar consumo
                      </button>

                      <button
                        type="button"
                        class="btn open-account-close"
                        data-account-id="${account.id}"
                      >
                        Cerrar y cobrar
                      </button>

                    </div>

                  </article>
                `
        )
        .join('')

      : `
              <div class="open-accounts-empty">
                <strong>
                  No hay cuentas abiertas
                </strong>

                <span>
                  Abre una mesa o zona VIP para comenzar.
                </span>
              </div>
            `
    }

      </div>
    </section>

    <div class="toolbar">
      <button class="btn" id="new-sale">+ Nueva venta</button>

      <button
        class="btn secondary"
        id="new-open-account"
        type="button"
      >
        + Abrir cuenta
      </button>

      <button
        class="btn secondary"
        id="repeat-last-sale"
        type="button"
      >
        ↻ Repetir última venta
      </button>

      <input class="input" placeholder="Buscar venta…" />

      <select class="select">
        <option>Este mes</option>
        <option>Hoy</option>
      </select>
    </div>

    
    <section
      class="card sales-filter-card"
      id="sales-history-filters"
      style="margin-bottom:14px"
    >

      <div class="sales-filter-head">

        <div>
          <p class="eyebrow">
            HISTORIAL
          </p>

          <h2>
            Filtrar ventas
          </h2>
        </div>

        <button
          type="button"
          class="btn secondary"
          id="clear-sales-filters"
        >
          Limpiar filtros
        </button>

      </div>


      <div class="sales-filter-grid">

        <label class="field">
          Desde
          <input
            type="date"
            id="sales-date-from"
          >
        </label>


        <label class="field">
          Hasta
          <input
            type="date"
            id="sales-date-to"
          >
        </label>


        <label class="field">
          Método de pago

          <select
            id="sales-payment-filter"
          >
            <option value="">
              Todos
            </option>

            <option value="efectivo">
              Efectivo
            </option>

            <option value="transferencia">
              Transferencia
            </option>

            <option value="tarjeta">
              Tarjeta
            </option>

            <option value="nequi">
              Nequi
            </option>

            <option value="daviplata">
              Daviplata
            </option>
          </select>

        </label>


        <label class="field">
          Estado

          <select
            id="sales-status-filter"
          >
            <option value="">
              Todos
            </option>

            <option value="completada">
              Completadas
            </option>

            <option value="anulada">
              Anuladas
            </option>
          </select>

        </label>

      </div>


      <div class="sales-filter-result">
        <span
          id="sales-filter-result-count"
        >
          0 ventas
        </span>
      </div>

    </section>

<section class="card">
      <table class="table">
        <thead>
          <tr>
            <th>Venta</th>
            <th>Detalle</th>
            <th>Fecha / hora</th>
            <th>Método</th>
            <th>Total</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>

        <tbody>
          ${state.sales.map(s => `
            <tr
              class="sale-history-row"
              data-sale-payment="${String(s.payment || '').toLowerCase()}"
              data-sale-status="${String(s.status || '').toLowerCase()}"
              data-sale-date="${s.created_at || ''}"
            >
              <td>
                <strong>
                  ${s.id}
                </strong>
              </td>

              <td>
                ${s.detail}
              </td>

              <td>
                <div class="sale-date-cell">
                  <strong>
                    ${saleDateTime(
      s.created_at
    ).date}
                  </strong>

                  <small>
                    ${saleDateTime(
      s.created_at
    ).time}
                  </small>
                </div>
              </td>

              <td>
                ${s.payment}
              </td>
              <td><strong>${money(s.total)}</strong></td>
              <td>
                <span class="pill ${
                  String(s.status).toUpperCase() === 'ANULADA'
                    ? 'red'
                    : 'green'
                }">
                  ${s.status}
                </span>
              </td>

              <td>
                <button
                  type="button"
                  class="btn secondary sale-detail-btn"
                  data-sale-id="${s.db_id}"
                >
                  Ver detalle
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </section>
  `;
}



/* ============================================================
   SALES FILTERS
============================================================ */

function normalizeSalesFilterText(
  value
) {

  return String(
    value || ''
  )
    .normalize('NFD')
    .replace(
      /[\u0300-\u036f]/g,
      ''
    )
    .toLowerCase()
    .trim();
}


function saleLocalDateValue(
  value
) {

  if (!value) {
    return '';
  }


  let normalized =
    String(value);


  if (
    !normalized.endsWith('Z')
    && !/[+-]\d{2}:\d{2}$/.test(
      normalized
    )
  ) {

    normalized += 'Z';
  }


  const date =
    new Date(
      normalized
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {

    return '';
  }


  const parts =
    new Intl.DateTimeFormat(
      'en-CA',
      {
        timeZone:
          'America/Bogota',

        year:
          'numeric',

        month:
          '2-digit',

        day:
          '2-digit'
      }
    )
      .formatToParts(
        date
      );


  const get =
    type =>
      parts.find(
        part =>
          part.type === type
      )?.value || '';


  return (
    `${get('year')}-`
    + `${get('month')}-`
    + `${get('day')}`
  );
}


function applySalesFilters() {

  const from =
    document.querySelector(
      '#sales-date-from'
    )?.value || '';


  const to =
    document.querySelector(
      '#sales-date-to'
    )?.value || '';


  const payment =
    normalizeSalesFilterText(
      document.querySelector(
        '#sales-payment-filter'
      )?.value
    );


  const status =
    normalizeSalesFilterText(
      document.querySelector(
        '#sales-status-filter'
      )?.value
    );


  const rows =
    [
      ...document.querySelectorAll(
        '.sale-history-row'
      )
    ];


  let visible = 0;


  rows.forEach(
    row => {

      const rowPayment =
        normalizeSalesFilterText(
          row.dataset.salePayment
        );


      const rowStatus =
        normalizeSalesFilterText(
          row.dataset.saleStatus
        );


      const date =
        saleLocalDateValue(
          row.dataset.saleDate
        );


      const matchesPayment =
        !payment
        || rowPayment === payment;


      const matchesStatus =
        !status
        || rowStatus === status;


      const matchesFrom =
        !from
        || (
          date
          && date >= from
        );


      const matchesTo =
        !to
        || (
          date
          && date <= to
        );


      const show =
        matchesPayment
        && matchesStatus
        && matchesFrom
        && matchesTo;


      row.style.display =
        show
          ? ''
          : 'none';


      if (show) {
        visible++;
      }

    }
  );


  const count =
    document.querySelector(
      '#sales-filter-result-count'
    );


  if (count) {

    count.textContent =
      `${visible} ${
        visible === 1
          ? 'venta'
          : 'ventas'
      }`;
  }


  if (
    typeof refreshCurrentViewPagination
    === 'function'
  ) {

    refreshCurrentViewPagination();
  }
}


function setupSalesFilters() {

  const container =
    document.querySelector(
      '#sales-history-filters'
    );


  if (!container) {
    return;
  }


  [
    '#sales-date-from',
    '#sales-date-to',
    '#sales-payment-filter',
    '#sales-status-filter'
  ]
    .forEach(
      selector => {

        const element =
          document.querySelector(
            selector
          );


        if (!element) {
          return;
        }


        element.addEventListener(
          'change',
          applySalesFilters
        );


        if (
          element.type === 'date'
        ) {

          element.addEventListener(
            'click',
            () => {

              if (
                typeof element.showPicker
                === 'function'
              ) {

                try {
                  element.showPicker();
                }
                catch {}
              }
            }
          );
        }
      }
    );


  document
    .querySelector(
      '#clear-sales-filters'
    )
    ?.addEventListener(
      'click',
      () => {

        [
          '#sales-date-from',
          '#sales-date-to',
          '#sales-payment-filter',
          '#sales-status-filter'
        ]
          .forEach(
            selector => {

              const input =
                document.querySelector(
                  selector
                );


              if (input) {
                input.value = '';
              }
            }
          );


        applySalesFilters();
      }
    );


  applySalesFilters();
}


/* ============================================================
   SALE DETAIL
============================================================ */

async function openSaleDetail(
  saleId
) {

  if (!saleId) {
    toast(
      'No se encontró el ID de la venta.'
    );
    return;
  }

  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/sales/${saleId}`
      );

    const data =
      await response
        .json()
        .catch(
          () => null
        );

    if (!response.ok) {
      throw new Error(
        data?.detail
        || 'No fue posible consultar la venta.'
      );
    }

    renderSaleDetailModal(
      data
    );

  }
  catch (error) {

    toast(
      error.message
    );
  }
}


function renderSaleDetailModal(
  sale
) {

  document
    .querySelector(
      '#sale-detail-modal'
    )
    ?.remove();


  const dateTime =
    saleDateTime(
      sale.created_at
    );


  const items =
    Array.isArray(
      sale.items
    )
      ? sale.items
      : [];


  const cancelled =
    String(
      sale.status || ''
    ).toUpperCase()
      === 'ANULADA';


  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="sale-detail-modal"
      >

        <div
          class="modal sale-detail-modal"
        >

          <div class="card-head">

            <div>

              <p class="eyebrow">
                DETALLE DE VENTA
              </p>

              <h2>
                ${sale.number}
              </h2>

              <small
                style="color:var(--muted)"
              >
                ${dateTime.date}
                ·
                ${dateTime.time}
              </small>

            </div>


            <button
              type="button"
              class="icon-btn"
              id="close-sale-detail"
            >
              ×
            </button>

          </div>


          <div class="sale-detail-meta">

            <div>
              <small>
                Cliente
              </small>

              <strong>
                ${
                  sale.customer_name
                  || 'Consumidor final'
                }
              </strong>
            </div>


            <div>
              <small>
                Método
              </small>

              <strong>
                ${
                  sale.payment_method
                  || '—'
                }
              </strong>
            </div>


            <div>
              <small>
                Estado
              </small>

              <span
                class="pill ${
                  cancelled
                    ? 'red'
                    : 'green'
                }"
              >
                ${sale.status}
              </span>
            </div>


            <div>
              <small>
                Total
              </small>

              <strong
                class="sale-detail-total"
              >
                ${money(
                  sale.total
                )}
              </strong>
            </div>

          </div>


          ${
            cancelled
              ? `
                  <div
                    class="sale-cancelled-info"
                  >

                    <strong>
                      Venta anulada
                    </strong>

                    <span>
                      ${
                        sale.cancellation_reason
                        || 'Sin motivo registrado'
                      }
                    </span>

                    ${
                      sale.cancelled_by_name
                        ? `
                            <small>
                              Anulada por:
                              ${sale.cancelled_by_name}
                            </small>
                          `
                        : ''
                    }

                  </div>
                `
              : ''
          }


          <div
            class="sale-detail-products"
          >

            <div
              class="sale-detail-products-head"
            >

              <strong>
                Productos vendidos
              </strong>

              <span class="pill">
                ${items.length}
              </span>

            </div>


            <div
              class="sale-detail-table-wrap"
            >

              <table class="table">

                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Cant.</th>
                    <th>Precio</th>
                    <th>Subtotal</th>
                  </tr>
                </thead>

                <tbody>

                  ${
                    items.length
                      ? items.map(
                          item => `
                            <tr>

                              <td>
                                <strong>
                                  ${item.product_name}
                                </strong>

                                <small>
                                  ${
                                    item.sku
                                    || 'Sin SKU'
                                  }
                                </small>
                              </td>

                              <td>
                                ${Number(
                                  item.quantity
                                )}
                              </td>

                              <td>
                                ${money(
                                  item.unit_price
                                )}
                              </td>

                              <td>
                                <strong>
                                  ${money(
                                    item.subtotal
                                  )}
                                </strong>
                              </td>

                            </tr>
                          `
                        ).join('')

                      : `
                          <tr>
                            <td
                              colspan="4"
                              class="empty"
                            >
                              No hay productos
                              registrados en esta venta.
                            </td>
                          </tr>
                        `
                  }

                </tbody>

              </table>

            </div>

          </div>


          <div
            class="sale-detail-grand-total"
          >

            <span>
              Total venta
            </span>

            <strong>
              ${money(
                sale.total
              )}
            </strong>

          </div>


          <div class="modal-actions">

            <button
              type="button"
              class="btn secondary"
              id="sale-detail-close-button"
            >
              Cerrar
            </button>

            ${
              !cancelled
              && state.currentUser?.role === 'ADMIN'
                ? `
                    <button
                      type="button"
                      class="btn qr-scan-btn"
                      id="generate-invoice-button"
                      data-sale-id="${sale.id}"
                    >
                      Generar factura electrónica
                    </button>

                    <button
                      type="button"
                      class="btn danger"
                      id="cancel-sale-button"
                    >
                      Anular venta
                    </button>
                  `
                : ''
            }

          </div>

        </div>

      </div>
    `
  );


  document
    .querySelector(
      '#close-sale-detail'
    )
    .onclick =
      closeSaleDetailModal;


  document
    .querySelector(
      '#sale-detail-close-button'
    )
    .onclick =
      closeSaleDetailModal;


  const cancelButton =
    document.querySelector(
      '#cancel-sale-button'
    );

  if (cancelButton) {

    cancelButton.onclick =
      () => {
        openCancelSaleModal(
          sale
        );
      };
  }

  const invoiceButton =
    document.querySelector(
      '#generate-invoice-button'
    );

  if (invoiceButton) {

    invoiceButton.onclick =
      async () => {
        invoiceButton.disabled = true;
        invoiceButton.textContent = 'Generando...';

        try {
          await generateSaleElectronicInvoice(sale.id);
          closeSaleDetailModal();
          await loadElectronicInvoices();
          render('invoices');
        } catch {
          invoiceButton.disabled = false;
          invoiceButton.textContent = 'Generar factura electrónica';
        }
      };
  }


  document
    .querySelector(
      '#sale-detail-modal'
    )
    .addEventListener(
      'click',
      event => {

        if (
          event.target.id
          === 'sale-detail-modal'
        ) {
          closeSaleDetailModal();
        }
      }
    );
}


function closeSaleDetailModal() {

  document
    .querySelector(
      '#sale-detail-modal'
    )
    ?.remove();
}



/* ============================================================
   SALE CANCELLATION
============================================================ */

function openCancelSaleModal(
  sale
) {

  if (
    state.currentUser?.role
    !== 'ADMIN'
  ) {

    toast(
      'Solo un administrador puede anular ventas.'
    );

    return;
  }


  document
    .querySelector(
      '#cancel-sale-modal'
    )
    ?.remove();


  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="cancel-sale-modal"
      >

        <div
          class="modal cancel-sale-modal"
        >

          <div class="card-head">

            <div>

              <p class="eyebrow">
                CONTROL ADMINISTRATIVO
              </p>

              <h2>
                Anular ${sale.number}
              </h2>

            </div>


            <button
              type="button"
              class="icon-btn"
              id="close-cancel-sale"
            >
              ×
            </button>

          </div>


          <div class="cancel-sale-warning">

            <strong>
              Esta acción afectará el inventario
            </strong>

            <p>
              Los productos de esta venta
              serán devueltos automáticamente
              al stock.
            </p>

            <p>
              La venta no será eliminada.
              Quedará marcada como
              <strong>ANULADA</strong>
              y el movimiento quedará registrado
              en auditoría.
            </p>

          </div>


          <label class="field full">

            Motivo de la anulación

            <textarea
              id="cancel-sale-reason"
              rows="4"
              maxlength="500"
              placeholder="Ej: Venta registrada por error, devolución autorizada..."
            ></textarea>

            <small>
              Obligatorio · mínimo 4 caracteres
            </small>

          </label>


          <div class="cancel-sale-summary">

            <span>
              Venta
            </span>

            <strong>
              ${sale.number}
            </strong>


            <span>
              Total
            </span>

            <strong>
              ${money(
                sale.total
              )}
            </strong>

          </div>


          <div class="modal-actions">

            <button
              type="button"
              class="btn secondary"
              id="cancel-sale-back"
            >
              Volver
            </button>


            <button
              type="button"
              class="btn danger"
              id="confirm-cancel-sale"
            >
              Confirmar anulación
            </button>

          </div>

        </div>

      </div>
    `
  );


  const close =
    () => {

      document
        .querySelector(
          '#cancel-sale-modal'
        )
        ?.remove();
    };


  document
    .querySelector(
      '#close-cancel-sale'
    )
    .onclick =
      close;


  document
    .querySelector(
      '#cancel-sale-back'
    )
    .onclick =
      close;


  document
    .querySelector(
      '#cancel-sale-modal'
    )
    .addEventListener(
      'click',
      event => {

        if (
          event.target.id
          === 'cancel-sale-modal'
        ) {

          close();
        }
      }
    );


  document
    .querySelector(
      '#confirm-cancel-sale'
    )
    .onclick =
      () =>
        confirmCancelSale(
          sale.id
        );


  setTimeout(
    () => {

      document
        .querySelector(
          '#cancel-sale-reason'
        )
        ?.focus();

    },
    50
  );
}


async function confirmCancelSale(
  saleId
) {

  if (
    state.currentUser?.role
    !== 'ADMIN'
  ) {

    toast(
      'No tienes permisos para anular ventas.'
    );

    return;
  }


  const reason =
    document
      .querySelector(
        '#cancel-sale-reason'
      )
      ?.value
      ?.trim()
      || '';


  if (
    reason.length < 4
  ) {

    toast(
      'Escribe un motivo de al menos 4 caracteres.'
    );

    return;
  }


  const button =
    document.querySelector(
      '#confirm-cancel-sale'
    );


  if (button) {

    button.disabled = true;
    button.textContent =
      'Anulando...';
  }


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/sales/${saleId}/cancel`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body: JSON.stringify({
            reason
          })
        }
      );


    const data =
      await response
        .json()
        .catch(
          () => null
        );


    if (!response.ok) {

      throw new Error(
        data?.detail
        || 'No fue posible anular la venta.'
      );
    }


    document
      .querySelector(
        '#cancel-sale-modal'
      )
      ?.remove();


    document
      .querySelector(
        '#sale-detail-modal'
      )
      ?.remove();


    toast(
      'Venta anulada. El inventario fue restaurado.'
    );


    /*
      Recargamos el estado completo
      para refrescar:
      - ventas
      - inventario
      - notificaciones de stock
      - dashboard
    */
    setTimeout(
      () => {
        window.location.reload();
      },
      650
    );


  }
  catch (error) {

    toast(
      error.message
    );


    if (button) {

      button.disabled = false;
      button.textContent =
        'Confirmar anulación';
    }
  }
}


/* ============================================================
   SALE DETAIL EVENTS
============================================================ */

document.addEventListener(
  'click',
  event => {

    const button =
      event.target.closest(
        '.sale-detail-btn'
      );


    if (!button) {
      return;
    }


    event.preventDefault();


    openSaleDetail(
      Number(
        button.dataset.saleId
      )
    );
  }
);


/* ============================================================
   INVENTORY
============================================================ */


/* ============================================================
   STOCK NOTIFICATIONS
============================================================ */

function getStockNotifications() {

  return (state.products || [])
    .filter(
      product =>
        product.id != null
    )
    .map(
      product => {

        const stock =
          Number(
            product.stock || 0
          );

        const minimum =
          Number(
            product.minimum_stock || 0
          );


        if (stock <= 0) {

          return {
            ...product,
            notification_type:
              'OUT_OF_STOCK',
            stock,
            minimum
          };
        }


        if (
          minimum > 0
          && stock <= minimum
        ) {

          return {
            ...product,
            notification_type:
              'LOW_STOCK',
            stock,
            minimum
          };
        }


        return null;
      }
    )
    .filter(Boolean)
    .sort(
      (a, b) => {

        if (
          a.notification_type
          !== b.notification_type
        ) {
          return (
            a.notification_type
              === 'OUT_OF_STOCK'
              ? -1
              : 1
          );
        }

        return (
          a.stock
          - b.stock
        );
      }
    );
}


function renderStockNotifications() {

  const badge =
    document.querySelector(
      '#stock-notification-badge'
    );

  const counter =
    document.querySelector(
      '#stock-notification-count'
    );

  const list =
    document.querySelector(
      '#stock-notification-list'
    );


  if (
    !badge
    || !counter
    || !list
  ) {
    return;
  }


  const notifications =
    getStockNotifications();


  const count =
    notifications.length;


  badge.textContent =
    String(count);

  badge.hidden =
    count === 0;

  counter.textContent =
    String(count);


  if (!count) {

    list.innerHTML = `
      <div class="stock-notification-empty">

        <strong>
          Inventario al día
        </strong>

        <span>
          No hay productos con stock bajo o agotado.
        </span>

      </div>
    `;

    return;
  }


  list.innerHTML =
    notifications
      .map(
        product => {

          const exhausted =
            product.notification_type
            === 'OUT_OF_STOCK';


          return `
            <button
              type="button"
              class="
                stock-notification-item
                ${exhausted
              ? 'is-out'
              : 'is-low'
            }
              "
              data-stock-notification-product="${product.id}"
            >

              <span
                class="stock-notification-icon"
              >
                ${exhausted
              ? '!'
              : '↓'
            }
              </span>


              <span
                class="stock-notification-content"
              >

                <strong>
                  ${product.name}
                </strong>

                <small>
                  ${exhausted
              ? 'Producto agotado'
              : 'Quedan pocas unidades'
            }
                </small>

                <span>
                  Stock:
                  <b>
                    ${product.stock}
                  </b>

                  ${Number(
              product.minimum_stock
            ) > 0
              ? `
                          · aviso en
                          <b>
                            ${Number(
                product.minimum_stock
              )}
                          </b>
                        `
              : ''
            }
                </span>

              </span>

            </button>
          `;
        }
      )
      .join('');
}


function openStockNotificationPanel() {

  const panel =
    document.querySelector(
      '#stock-notification-panel'
    );

  const button =
    document.querySelector(
      '#stock-notification-button'
    );

  const overlay =
    document.querySelector(
      '#notif-overlay'
    );


  if (!panel) {
    return;
  }

  // Close drawer if open
  const mobileDrawer =
    document.querySelector(
      '#mobile-drawer'
    );
  const drawerOverlay =
    document.querySelector(
      '#drawer-overlay'
    );
  const hamburgerBtn =
    document.querySelector(
      '#hamburger-btn'
    );
  if (mobileDrawer?.classList.contains('open')) {
    mobileDrawer.classList.remove('open');
    drawerOverlay?.classList.remove('open');
    if (drawerOverlay) drawerOverlay.hidden = true;
    hamburgerBtn?.classList.remove('open');
    hamburgerBtn?.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
  }

  // Close user dropdown if open
  const userDropdown =
    document.querySelector(
      '#mobile-user-dropdown'
    );
  if (userDropdown) {
    userDropdown.hidden = true;
  }


  renderStockNotifications();


  panel.hidden = false;
  if (overlay) {
    overlay.hidden = false;
    overlay.classList.add('open');
  }
  document.body.classList.add('notifications-open');


  button?.setAttribute(
    'aria-expanded',
    'true'
  );

  // Focus the close button
  const closeBtn = document.querySelector('#stock-notification-close');
  if (closeBtn) closeBtn.focus();
}


function closeStockNotificationPanel() {

  const panel =
    document.querySelector(
      '#stock-notification-panel'
    );

  const button =
    document.querySelector(
      '#stock-notification-button'
    );

  const overlay =
    document.querySelector(
      '#notif-overlay'
    );


  if (panel) {
    panel.hidden = true;
  }
  if (overlay) {
    overlay.hidden = true;
    overlay.classList.remove('open');
  }
  document.body.classList.remove('notifications-open');


  button?.setAttribute(
    'aria-expanded',
    'false'
  );

  // Return focus to bell button
  if (button) button.focus();
}


function toggleStockNotificationPanel() {

  const panel =
    document.querySelector(
      '#stock-notification-panel'
    );


  if (!panel) {
    return;
  }


  if (panel.hidden) {
    openStockNotificationPanel();
  }
  else {
    closeStockNotificationPanel();
  }
}


/* ============================================================
   STOCK NOTIFICATION EVENTS
============================================================ */

document.addEventListener(
  'click',
  event => {

    const notificationButton =
      event.target.closest(
        '#stock-notification-button'
      );


    if (notificationButton) {

      event.preventDefault();
      event.stopPropagation();

      toggleStockNotificationPanel();

      return;
    }


    const inventoryButton =
      event.target.closest(
        '#stock-notification-inventory'
      );


    if (inventoryButton) {

      event.preventDefault();

      closeStockNotificationPanel();

      render(
        'inventory'
      );

      return;
    }


    const notifCloseBtn =
      event.target.closest(
        '#stock-notification-close'
      );


    if (notifCloseBtn) {

      event.preventDefault();

      closeStockNotificationPanel();

      return;
    }


    const notifOverlay =
      event.target.closest(
        '#notif-overlay'
      );


    if (notifOverlay) {

      event.preventDefault();

      closeStockNotificationPanel();

      return;
    }


    const productItem =
      event.target.closest(
        '[data-stock-notification-product]'
      );


    if (productItem) {

      event.preventDefault();

      closeStockNotificationPanel();

      render(
        'inventory'
      );

      return;
    }


    const panel =
      document.querySelector(
        '#stock-notification-panel'
      );


    if (
      panel
      && !panel.hidden
      && !event.target.closest(
        '#stock-notification-panel'
      )
    ) {

      closeStockNotificationPanel();
    }

  }
);


/* Escape key closes notifications */
document.addEventListener(
  'keydown',
  event => {

    if (event.key === 'Escape') {

      const panel =
        document.querySelector(
          '#stock-notification-panel'
        );

      if (panel && !panel.hidden) {
        event.preventDefault();
        closeStockNotificationPanel();
      }
    }
  }
);


function inventory() {

  const adminProducts =
    state.products.filter(
      product => product.id != null
    );

  const adminProductPanel = `
    <section class="card">
      <div class="card-head">
        <div>
          <p class="eyebrow">
            ADMINISTRADOR
          </p>

          <h2>
            Productos y códigos QR
          </h2>
        </div>

        <span class="pill green">
          Acceso restringido
        </span>
      </div>

      <p style="opacity:.72">
        Crear productos, eliminarlos y generar
        códigos QR requiere autorización de administrador.
      </p>

      <div
        class="form-grid"
        style="margin-top:18px"
      >
        <label class="field full">
          Producto

          <select id="admin-product-select">
            ${adminProducts.map(product => `
              <option value="${product.id}">
                ${product.name}
                ${product.sku
      ? ` · ${product.sku}`
      : ''}
              </option>
            `).join('')}
          </select>
        </label>

        <div
          class="field full"
          style="
            display:flex;
            gap:10px;
            flex-wrap:wrap;
          "
        >
          <button
            type="button"
            class="btn primary"
            id="admin-generate-qr"
          >
            Generar / ver QR
          </button>

          <button
            type="button"
            class="btn qr-scan-btn"
            id="admin-scan-qr"
          >
            Escanear QR
          </button>

          <button
            type="button"
            class="btn secondary"
            id="admin-delete-product"
          >
            Eliminar producto
          </button>

          <button
            type="button"
            class="btn secondary"
            id="admin-clear-session"
          >
            Cerrar acceso admin
          </button>
        </div>
      </div>
    </section>
  `;

  const movementRows = state.inventoryMovements.length
    ? state.inventoryMovements.map(m => `
        <tr>
          <td>
            <strong>${m.product_name}</strong>
            <small>${m.notes || ''}</small>
          </td>

          <td>
            <span class="pill ${Number(m.quantity) < 0 ? 'yellow' : 'green'
      }">
              ${m.movement_type}
            </span>
          </td>

          <td>
            <strong>${Number(m.quantity)}</strong>
          </td>

          <td>${Number(m.previous_stock)}</td>

          <td>
            <strong>${Number(m.new_stock)}</strong>
          </td>

          <td>
            ${m.reference_type && m.reference_id
        ? `${m.reference_type} #${m.reference_id}`
        : '—'
      }
          </td>

          <td>
            ${m.created_at
        ? new Date(m.created_at).toLocaleString('es-CO')
        : '—'
      }
          </td>
        </tr>
      `).join('')
    : `
        <tr>
          <td colspan="7" class="empty">
            Aún no hay movimientos de inventario registrados.
          </td>
        </tr>
      `;

  return `
    ${adminProductPanel}

    <div class="toolbar inventory-toolbar">
      <button class="btn" id="new-product">
        + Agregar producto
      </button>

      <button class="btn secondary" id="new-adjustment">
        + Registrar movimiento
      </button>

      <input
        class="input"
        id="inventory-search"
        type="search"
        placeholder="Buscar por nombre o SKU…"
        autocomplete="off"
      />

      <select
        class="input"
        id="inventory-stock-filter"
      >
        <option value="all">
          Todo el stock
        </option>

        <option value="low">
          Stock bajo
        </option>

        <option value="available">
          Disponible
        </option>
      </select>

      <select
        class="input"
        id="inventory-qr-filter"
      >
        <option value="all">
          Todos los QR
        </option>

        <option value="with">
          Con QR
        </option>

        <option value="without">
          Sin QR
        </option>
      </select>

      <select
        class="input"
        id="inventory-sort"
      >
        <option value="name-asc">
          Nombre A-Z
        </option>

        <option value="name-desc">
          Nombre Z-A
        </option>

        <option value="stock-asc">
          Stock menor
        </option>

        <option value="stock-desc">
          Stock mayor
        </option>

        <option value="price-asc">
          Precio menor
        </option>

        <option value="price-desc">
          Precio mayor
        </option>
      </select>
    </div>

    <section class="card">
      <div class="card-head">
        <h2>Inventario actual</h2>
        <span class="pill">
          ${state.products.length} productos
        </span>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Existencia</th>
            <th>Unidad</th>
            <th>Precio venta</th>
            <th>Estado</th>
            <th>QR / Acciones</th>
          </tr>
        </thead>

        <tbody>
          ${state.products.map(p => `
            <tr
              class="inventory-product-row"
              data-product-search="${(
      `${p.name || ''} ${p.sku || ''}`
    ).toLowerCase()}"
              data-product-name="${(
      p.name || ''
    ).toLowerCase()}"
              data-product-stock="${Number(
      p.stock || 0
    )}"
              data-product-price="${Number(
      p.price || 0
    )}"
              data-stock-status="${Number(p.stock) <= 0
      ? 'out'
      : Number(p.minimum_stock || 0) > 0
        && Number(p.stock) <= Number(p.minimum_stock)
        ? 'low'
        : 'available'
    }"
              data-qr-status="${p.has_qr
      ? 'with'
      : 'without'
    }"
            >
              <td>
                <div class="product-name-cell">
                  ${p.image_url
      ? `<img src="${p.image_url}" alt="" class="product-thumb" />`
      : `<span class="product-thumb product-thumb-empty">♪</span>`
    }
                  <div>
                    <strong>${p.name}</strong>
                    <small>${p.sku || 'Sin SKU'}</small>
                  </div>
                </div>
              </td>

              <td>${Number(p.stock)}</td>

              <td>${p.unit}</td>

              <td>${money(p.price)}</td>

              <td>
                <span class="pill ${Number(p.stock) <= 0
      ? 'red'
      : Number(p.minimum_stock || 0) > 0
        && Number(p.stock) <= Number(p.minimum_stock)
        ? 'yellow'
        : 'green'
    }">
                  ${Number(p.stock) <= 0
      ? 'Agotado'
      : Number(p.minimum_stock || 0) > 0
        && Number(p.stock) <= Number(p.minimum_stock)
        ? 'Stock bajo'
        : 'Disponible'
    }
                </span>
              </td>

              <td>
                <span
                  class="pill ${p.has_qr ? 'green' : 'yellow'}"
                >
                  ${p.has_qr
      ? 'QR activo'
      : 'Sin QR'
    }
                </span>
              </td>

              <td>
                <div
                  style="
                    display:flex;
                    gap:8px;
                    flex-wrap:wrap;
                  "
                >
                  <button
                    class="btn secondary product-qr-btn"
                    data-product-id="${p.id}"
                    type="button"
                  >
                    ${p.has_qr
      ? 'Ver QR'
      : 'Generar QR'
    }
                  </button>

                  <button
                    class="btn secondary product-delete-qr-btn"
                    data-product-id="${p.id}"
                    type="button"
                    ${p.has_qr ? '' : 'disabled'}
                  >
                    Eliminar QR
                  </button>

                  <button
                    class="btn secondary product-delete-btn"
                    data-product-id="${p.id}"
                    type="button"
                  >
                    Eliminar producto
                  </button>

                  <button
                    class="btn secondary product-edit-btn"
                    data-product-id="${p.id}"
                    type="button"
                  >
                    Editar
                  </button>
                </div>
              </td>
            </tr>
          `).join('')}

          <tr
            id="inventory-search-empty"
            style="display:none"
          >
            <td
              colspan="7"
              class="empty"
            >
              No se encontraron productos.
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card inventory-history" style="margin-top:18px">
      <div class="card-head">
        <div>
          <h2>Historial de movimientos</h2>

          <small style="color:var(--muted)">
            Entradas y salidas registradas en el inventario
          </small>
        </div>

        <span class="pill">
          ${state.inventoryMovements.length} movimientos
        </span>
      </div>

      <div class="inventory-history-table">
        <table
          class="table"
          id="inventory-movements-table"
          data-pagination-key="inventory-movements"
        >
          <thead>
            <tr>
              <th>Producto</th>
              <th>Tipo</th>
              <th>Cantidad</th>
              <th>Stock anterior</th>
              <th>Stock nuevo</th>
              <th>Referencia</th>
              <th>Fecha</th>
            </tr>
          </thead>

          <tbody>
            ${movementRows}
          </tbody>
        </table>
      </div>

      <div class="inventory-history-mobile">
        ${state.inventoryMovements.length
      ? state.inventoryMovements.map(m => `
                    <article class="movement-card">
                      <div class="movement-card-head">
                        <div>
                          <strong>${m.product_name}</strong>

                          <small>
                            ${m.notes || 'Movimiento de inventario'}
                          </small>
                        </div>

                        <span class="pill ${Number(m.quantity) < 0
          ? 'yellow'
          : 'green'
        }">
                          ${m.movement_type}
                        </span>
                      </div>

                      <div class="movement-card-grid">

                        <div>
                          <small>Cantidad</small>
                          <strong>
                            ${Number(m.quantity) > 0 ? '+' : ''}
                            ${Number(m.quantity)}
                          </strong>
                        </div>

                        <div>
                          <small>Stock anterior</small>
                          <strong>
                            ${Number(m.previous_stock)}
                          </strong>
                        </div>

                        <div>
                          <small>Stock nuevo</small>
                          <strong>
                            ${Number(m.new_stock)}
                          </strong>
                        </div>

                        <div>
                          <small>Referencia</small>
                          <strong>
                            ${m.reference_type &&
          m.reference_id
          ? `${m.reference_type} #${m.reference_id}`
          : '—'
        }
                          </strong>
                        </div>

                      </div>

                      <div class="movement-card-date">
                        ${m.created_at
          ? new Date(
            m.created_at
          ).toLocaleString('es-CO')
          : 'Sin fecha'
        }
                      </div>
                    </article>
                  `).join('')
      : `
                    <div class="empty">
                      Aún no hay movimientos de inventario registrados.
                    </div>
                  `
    }
      </div>
    </section>
  `;
}

/* ============================================================
   EXPENSES
============================================================ */

function expenses() {
  return `
    <div class="toolbar">
      <button class="btn" id="new-expense">+ Registrar gasto</button>

      <select class="select">
        <option>Todos los gastos</option>
        <option>Este mes</option>
      </select>
    </div>

    <section class="card">
      <table class="table expenses-table">
        <thead>
          <tr>
            <th>Concepto</th>
            <th>Proveedor</th>
            <th>Fecha</th>
            <th>Valor</th>
          </tr>
        </thead>

        <tbody>
          ${state.expenses.map(e => `
            <tr>
              <td><strong>${e.concept}</strong></td>
              <td>${e.provider}</td>
              <td>${e.date}</td>
              <td><strong>${money(e.value)}</strong></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </section>
  `;
}


/* ============================================================
   ELECTRONIC INVOICES VIEW
============================================================ */

let electronicInvoicesLoaded = false;
let electronicInvoices = [];

async function loadElectronicInvoices() {
  try {
    const response = await adminFetch(
      `${API_BASE}/api/electronic-invoices?limit=200`
    );

    if (response.ok) {
      electronicInvoices = await response.json();
      electronicInvoicesLoaded = true;
    }
  } catch { }
}

let companyInfoData = null;

async function loadCompanyInfo() {
  try {
    const response = await adminFetch(
      `${API_BASE}/api/company-info`
    );

    if (response.ok) {
      companyInfoData = await response.json();
    }
  } catch { }
}

function getInvoiceStatusLabel(status) {
  const labels = {
    DRAFT: 'Borrador',
    GENERATED: 'Generada',
    SIGNED: 'Firmada',
    SENDING: 'Enviando',
    PENDING: 'Pendiente',
    SENT: 'Enviada',
    ACCEPTED: 'Aceptada',
    REJECTED: 'Rechazada',
    ERROR: 'Error',
  };
  return labels[status] || status || 'Desconocido';
}

function getInvoiceStatusClass(status) {
  const classes = {
    DRAFT: '',
    GENERATED: '',
    SIGNED: '',
    SENDING: 'yellow',
    PENDING: 'yellow',
    SENT: 'yellow',
    ACCEPTED: 'green',
    REJECTED: 'red',
    ERROR: 'red',
  };
  return classes[status] || '';
}

function invoicesView() {
  const rows = electronicInvoices.length
    ? electronicInvoices.map(inv => `
        <tr>
          <td>
            <strong>${inv.invoice_number || '—'}</strong>
          </td>
          <td>${inv.prefix || 'FE'}</td>
          <td>${inv.customer_name || 'Consumidor final'}</td>
          <td><strong>${money(inv.total)}</strong></td>
          <td>
            <span class="pill ${getInvoiceStatusClass(inv.status)}">
              ${getInvoiceStatusLabel(inv.status)}
            </span>
          </td>
          <td>
            ${inv.environment === 'sandbox' || inv.environment === 'habilitacion'
      ? '<span class="pill yellow">HABILITACIÓN</span>'
      : inv.environment === 'produccion'
        ? '<span class="pill red">PRODUCCIÓN</span>'
        : '<span class="pill">SIMULADOR</span>'
    }
          </td>
          <td>
            ${inv.issued_at
      ? new Date(inv.issued_at).toLocaleString('es-CO')
      : inv.created_at
        ? new Date(inv.created_at).toLocaleString('es-CO')
        : '—'
    }
          </td>
          <td>
            <button
              class="btn secondary invoice-detail-btn"
              data-invoice-id="${inv.id}"
              type="button"
            >
              Ver detalle
            </button>
          </td>
        </tr>
      `).join('')
    : `
        <tr>
          <td colspan="8" class="empty">
            Aún no hay facturas electrónicas registradas.
          </td>
        </tr>
      `;

  return `
    <section class="card">
      <div class="card-head">
        <div>
          <p class="eyebrow">ADMINISTRADOR</p>
          <h2>Facturación electrónica</h2>
        </div>
        <span class="pill">
          ${electronicInvoices.length} facturas
        </span>
      </div>

      <p style="opacity:.72;margin-bottom:16px;">
        Las facturas electrónicas se generan desde el detalle de cada venta.
        ${!electronicInvoicesLoaded
      ? '<br><small style="color:var(--yellow);">Cargando facturas...</small>'
      : ''
    }
      </p>

      <div class="invoice-env-banner">
        <strong>AMBIENTE DE HABILITACIÓN DIAN</strong>
        <small>
          Las facturas generadas en este ambiente son válidas solo para pruebas.
          Para facturación real, configure DIAN_ENVIRONMENT=produccion con credenciales válidas.
        </small>
      </div>

      <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;">
        <button type="button" class="btn secondary" id="open-company-info-btn">
          Configurar datos fiscales
        </button>
      </div>
    </section>

    <section class="card" style="margin-top:18px;">
      <div class="card-head">
        <h2>Historial de facturas</h2>
      </div>

      <div class="table-responsive">
        <table class="table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Prefijo</th>
              <th>Cliente</th>
              <th>Total</th>
              <th>Estado</th>
              <th>Ambiente</th>
              <th>Fecha</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

async function openInvoiceDetail(invoiceId) {
  try {
    const response = await adminFetch(
      `${API_BASE}/api/electronic-invoices/${invoiceId}`
    );

    if (!response.ok) {
      toast('No fue posible cargar la factura.');
      return;
    }

    const inv = await response.json();
    showInvoiceDetailModal(inv);
  } catch {
    toast('Error al cargar el detalle de la factura.');
  }
}

async function openCompanyInfoModal() {
  await loadCompanyInfo();

  const info = companyInfoData || {};

  document.querySelector('#company-info-modal')?.remove();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="company-info-modal">
        <div class="modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">DATOS FISCALES</p>
              <h2>Información del emisor</h2>
            </div>
            <button type="button" class="icon-btn" id="close-company-info-modal">×</button>
          </div>

          <p style="opacity:.72;margin-bottom:14px;font-size:13px;">
            Datos necesarios para la facturación electrónica.
            Esta información se usa como emisor en todas las facturas.
          </p>

          <div class="form-grid">
            <label class="field full">
              Razón social
              <input id="ci-company-name" maxlength="200" value="${String(info.company_name || '').replace(/"/g, '&quot;')}" placeholder="Mi Empresa S.A.S." />
            </label>

            <label class="field">
              NIT
              <input id="ci-nit" maxlength="30" value="${String(info.nit || '').replace(/"/g, '&quot;')}" placeholder="900123456" />
            </label>

            <label class="field">
              DV
              <input id="ci-dv" maxlength="5" value="${String(info.dv || '').replace(/"/g, '&quot;')}" placeholder="7" />
            </label>

            <label class="field full">
              Dirección
              <input id="ci-address" maxlength="250" value="${String(info.address || '').replace(/"/g, '&quot;')}" placeholder="Calle 10 #5-20" />
            </label>

            <label class="field">
              Municipio
              <input id="ci-municipality" maxlength="100" value="${String(info.municipality || '').replace(/"/g, '&quot;')}" placeholder="Bogotá D.C." />
            </label>

            <label class="field">
              Departamento
              <input id="ci-department" maxlength="100" value="${String(info.department || '').replace(/"/g, '&quot;')}" placeholder="Bogotá D.C." />
            </label>

            <label class="field">
              Teléfono
              <input id="ci-phone" maxlength="40" value="${String(info.phone || '').replace(/"/g, '&quot;')}" placeholder="6011234567" />
            </label>

            <label class="field">
              Email
              <input id="ci-email" maxlength="160" type="email" value="${String(info.email || '').replace(/"/g, '&quot;')}" placeholder="facturacion@empresa.com" />
            </label>

            <label class="field">
              Régimen
              <input id="ci-regime" maxlength="50" value="${String(info.regime || '').replace(/"/g, '&quot;')}" placeholder="Responsable de IVA" />
            </label>

            <label class="field">
              Prefijo facturación
              <input id="ci-resolution-prefix" maxlength="20" value="${String(info.resolution_prefix || '').replace(/"/g, '&quot;')}" placeholder="FE" />
            </label>

            <label class="field">
              Resolución N°
              <input id="ci-resolution-number" maxlength="80" value="${String(info.resolution_number || '').replace(/"/g, '&quot;')}" placeholder="18920000001" />
            </label>

            <label class="field">
              Rango desde
              <input id="ci-resolution-range-from" type="number" min="1" value="${info.resolution_range_from || ''}" placeholder="1" />
            </label>

            <label class="field">
              Rango hasta
              <input id="ci-resolution-range-to" type="number" min="1" value="${info.resolution_range_to || ''}" placeholder="5000" />
            </label>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn secondary" id="cancel-company-info">Cancelar</button>
            <button type="button" class="btn" id="save-company-info">Guardar</button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-company-info-modal')
    ?.addEventListener('click', () => {
      document.querySelector('#company-info-modal')?.remove();
    });

  document.querySelector('#cancel-company-info')
    ?.addEventListener('click', () => {
      document.querySelector('#company-info-modal')?.remove();
    });

  document.querySelector('#company-info-modal')
    ?.addEventListener('click', e => {
      if (e.target.id === 'company-info-modal') {
        e.target.remove();
      }
    });

  document.querySelector('#save-company-info')
    ?.addEventListener('click', async () => {
      const companyName = document.querySelector('#ci-company-name')?.value?.trim();
      const nit = document.querySelector('#ci-nit')?.value?.trim();

      if (!companyName || companyName.length < 2) {
        toast('Ingresa la razón social.');
        return;
      }

      if (!nit || nit.length < 3) {
        toast('Ingresa el NIT.');
        return;
      }

      const payload = {
        company_name: companyName,
        nit: nit,
        dv: document.querySelector('#ci-dv')?.value?.trim() || null,
        address: document.querySelector('#ci-address')?.value?.trim() || null,
        municipality: document.querySelector('#ci-municipality')?.value?.trim() || null,
        department: document.querySelector('#ci-department')?.value?.trim() || null,
        phone: document.querySelector('#ci-phone')?.value?.trim() || null,
        email: document.querySelector('#ci-email')?.value?.trim() || null,
        regime: document.querySelector('#ci-regime')?.value?.trim() || null,
        resolution_prefix: document.querySelector('#ci-resolution-prefix')?.value?.trim() || null,
        resolution_number: document.querySelector('#ci-resolution-number')?.value?.trim() || null,
        resolution_range_from: Number(document.querySelector('#ci-resolution-range-from')?.value) || null,
        resolution_range_to: Number(document.querySelector('#ci-resolution-range-to')?.value) || null,
      };

      const saveBtn = document.querySelector('#save-company-info');
      saveBtn.disabled = true;
      saveBtn.textContent = 'Guardando...';

      try {
        const method = companyInfoData?.id ? 'PUT' : 'POST';

        const response = await adminFetch(
          `${API_BASE}/api/company-info`,
          {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          }
        );

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || 'No fue posible guardar la información.');
        }

        toast('Información fiscal guardada correctamente.');
        await loadCompanyInfo();
        document.querySelector('#company-info-modal')?.remove();

      } catch (error) {
        toast(error.message);
        saveBtn.disabled = false;
        saveBtn.textContent = 'Guardar';
      }
    });
}


function showInvoiceDetailModal(inv) {
  document.querySelector('#invoice-detail-modal')?.remove();

  const items = inv.items || [];

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="invoice-detail-modal">
        <div class="modal modal-lg">
          <div class="card-head">
            <div>
              <p class="eyebrow">FACTURA ELECTRÓNICA</p>
              <h2>${inv.invoice_number || '—'}</h2>
            </div>
            <button type="button" class="icon-btn" id="close-invoice-detail">×</button>
          </div>

          <div class="invoice-detail-grid">
            <div class="invoice-detail-section">
              <small class="eyebrow">ESTADO</small>
              <span class="pill ${getInvoiceStatusClass(inv.status)}" style="font-size:14px;">
                ${getInvoiceStatusLabel(inv.status)}
              </span>
              ${inv.environment === 'sandbox' || inv.environment === 'habilitacion'
      ? '<br><span class="pill yellow" style="margin-top:6px;">AMBIENTE DE HABILITACIÓN / PRUEBAS</span>'
      : inv.environment === 'produccion'
        ? '<br><span class="pill red" style="margin-top:6px;">PRODUCCIÓN</span>'
        : ''
    }
            </div>

            <div class="invoice-detail-section">
              <small class="eyebrow">CLIENTE</small>
              <strong>${inv.customer_name || 'Consumidor final'}</strong>
              ${inv.customer_document_number
      ? `<br><small>Doc: ${inv.customer_document_number}</small>`
      : ''
    }
              ${inv.customer_email
      ? `<br><small>Email: ${inv.customer_email}</small>`
      : ''
    }
            </div>

            <div class="invoice-detail-section">
              <small class="eyebrow">PROVEEDOR</small>
              <strong>${inv.provider === 'dian' ? 'DIAN Colombia' : inv.provider === 'mock' ? 'Simulador (pruebas)' : inv.provider || 'mock'}</strong>
              ${inv.provider_reference
      ? `<br><small>Ref: ${inv.provider_reference}</small>`
      : ''
    }
            </div>

            <div class="invoice-detail-section">
              <small class="eyebrow">FECHA</small>
              <strong>
                ${inv.issued_at
      ? new Date(inv.issued_at).toLocaleString('es-CO')
      : inv.created_at
        ? new Date(inv.created_at).toLocaleString('es-CO')
        : '—'
    }
              </strong>
            </div>
          </div>

          ${inv.cufe
      ? `<div class="invoice-cufe-box">
                <small class="eyebrow">CUFE</small>
                <code style="word-break:break-all;">${inv.cufe}</code>
              </div>`
      : ''
    }

          ${items.length
      ? `
            <div style="margin-top:16px;">
              <small class="eyebrow">DETALLE DE PRODUCTOS</small>
              <table class="table" style="margin-top:8px;">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Cant.</th>
                    <th>Precio</th>
                    <th>Subtotal</th>
                    <th>Impuesto</th>
                  </tr>
                </thead>
                <tbody>
                  ${items.map(item => `
                    <tr>
                      <td><strong>${item.product_name || '—'}</strong></td>
                      <td>${Number(item.quantity)}</td>
                      <td>${money(item.unit_price)}</td>
                      <td>${money(item.subtotal)}</td>
                      <td>
                        ${Number(item.tax_rate) > 0
      ? `${item.tax_type || 'IVA'} ${item.tax_rate}%`
      : 'Exento'
    }
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `
      : ''
    }

          <div class="invoice-totals-box">
            <div class="invoice-total-row">
              <span>Subtotal</span>
              <strong>${money(inv.subtotal)}</strong>
            </div>
            <div class="invoice-total-row">
              <span>Impuestos</span>
              <strong>${money(inv.tax_total)}</strong>
            </div>
            <div class="invoice-total-row invoice-total-final">
              <span>Total</span>
              <strong>${money(inv.total)}</strong>
            </div>
          </div>

          ${inv.error_message
      ? `<div class="invoice-error-box">
                <small class="eyebrow" style="color:var(--red);">ERROR</small>
                <p style="color:var(--red);font-size:13px;">
                  ${inv.error_message}
                </p>
              </div>`
      : ''
    }

          <div class="modal-actions">
            ${['DRAFT', 'GENERATED', 'SIGNED', 'ERROR'].includes(inv.status)
      ? `<button type="button" class="btn qr-scan-btn" id="send-invoice-btn" data-invoice-id="${inv.id}">
                  ${inv.status === 'ERROR' ? 'Reintentar envío' : 'Enviar a DIAN'}
                </button>`
      : ''
    }
            ${inv.provider_reference
      ? `<button type="button" class="btn secondary" id="download-xml-btn" data-invoice-id="${inv.id}">
                  Descargar XML
                </button>`
      : ''
    }
            <button type="button" class="btn secondary" id="close-invoice-detail-btn">
              Cerrar
            </button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-invoice-detail')
    ?.addEventListener('click', () => {
      document.querySelector('#invoice-detail-modal')?.remove();
    });

  document.querySelector('#close-invoice-detail-btn')
    ?.addEventListener('click', () => {
      document.querySelector('#invoice-detail-modal')?.remove();
    });

  document.querySelector('#send-invoice-btn')
    ?.addEventListener('click', async () => {
      const btn = document.querySelector('#send-invoice-btn');
      const invoiceId = btn?.dataset.invoiceId;
      if (!invoiceId) return;

      btn.disabled = true;
      btn.textContent = 'Enviando...';

      try {
        const response = await adminFetch(
          `${API_BASE}/api/electronic-invoices/${invoiceId}/send`,
          { method: 'POST' }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'No fue posible enviar la factura.');
        }

        toast(`Factura ${data.invoice_number}: ${getInvoiceStatusLabel(data.status)}`);

        await loadElectronicInvoices();
        document.querySelector('#invoice-detail-modal')?.remove();

      } catch (error) {
        toast(error.message);
        btn.disabled = false;
        btn.textContent = invoice?.status === 'ERROR' ? 'Reintentar envío' : 'Enviar a DIAN';
      }
    });

  document.querySelector('#download-xml-btn')
    ?.addEventListener('click', async () => {
      const btn = document.querySelector('#download-xml-btn');
      const invoiceId = btn?.dataset.invoiceId;
      if (!invoiceId) return;

      try {
        const response = await adminFetch(
          `${API_BASE}/api/electronic-invoices/${invoiceId}/xml`
        );

        if (!response.ok) {
          throw new Error('XML no disponible.');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `factura-${invoice?.invoice_number || invoiceId}.xml`;
        a.click();
        URL.revokeObjectURL(url);

      } catch (error) {
        toast(error.message);
      }
    });

  document.querySelector('#invoice-detail-modal')
    ?.addEventListener('click', e => {
      if (e.target.id === 'invoice-detail-modal') {
        e.target.remove();
      }
    });
}

async function generateSaleElectronicInvoice(saleId) {
  saleId = Number(saleId);

  try {
    const response = await adminFetch(
      `${API_BASE}/api/sales/${saleId}/electronic-invoice`,
      { method: 'POST' }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'No fue posible generar la factura electrónica.');
    }

    toast(
      `Factura ${data.invoice_number} generada. Estado: ${getInvoiceStatusLabel(data.status)}`
    );

    await loadElectronicInvoices();

    return data;

  } catch (error) {
    toast(error.message);
    throw error;
  }
}


/* ============================================================
   OPEN ACCOUNTS UI
============================================================ */

function openAccountModal() {

  document
    .querySelector(
      '#open-account-modal'
    )
    ?.remove();


  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="open-account-modal"
      >
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">
                CUENTA ABIERTA
              </p>

              <h2>
                Abrir nueva cuenta
              </h2>
            </div>

            <button
              class="icon-btn"
              id="close-open-account-modal"
              type="button"
            >
              ×
            </button>
          </div>


          <div class="form-grid">

            <label class="field">
              Tipo

              <select id="open-account-type">
                <option value="MESA">
                  Mesa
                </option>

                <option value="VIP">
                  Zona VIP
                </option>

                <option value="BARRA">
                  Barra
                </option>

                <option value="OTRO">
                  Otro
                </option>
              </select>
            </label>


            <label class="field">
              Identificador

              <input
                id="open-account-label"
                maxlength="80"
                placeholder="Ej. Mesa 04 o VIP 02"
              />
            </label>


            <label class="field">
              Zona

              <input
                id="open-account-zone"
                maxlength="80"
                placeholder="Ej. Piso 1, Terraza, VIP"
              />
            </label>


            <label class="field">
              Cliente

              <input
                id="open-account-customer"
                maxlength="160"
                value="Consumidor final"
              />
            </label>

          </div>


          <div class="modal-actions">

            <button
              class="btn secondary"
              id="cancel-open-account"
              type="button"
            >
              Cancelar
            </button>

            <button
              class="btn"
              id="save-open-account"
              type="button"
            >
              Abrir cuenta
            </button>

          </div>

        </div>
      </div>
    `
  );


  document
    .querySelector(
      '#close-open-account-modal'
    )
    .onclick =
    closeOpenAccountModal;

  document
    .querySelector(
      '#cancel-open-account'
    )
    .onclick =
    closeOpenAccountModal;

  document
    .querySelector(
      '#save-open-account'
    )
    .onclick =
    submitOpenAccount;


  document
    .querySelector(
      '#open-account-modal'
    )
    .addEventListener(
      'click',
      event => {

        if (
          event.target.id
          === 'open-account-modal'
        ) {
          closeOpenAccountModal();
        }
      }
    );


  setTimeout(
    () => {
      document
        .querySelector(
          '#open-account-label'
        )
        ?.focus();
    },
    0
  );
}


function closeOpenAccountModal() {

  document
    .querySelector(
      '#open-account-modal'
    )
    ?.remove();
}


async function submitOpenAccount() {

  const accountType =
    document
      .querySelector(
        '#open-account-type'
      )
      ?.value;

  const label =
    document
      .querySelector(
        '#open-account-label'
      )
      ?.value
      .trim();

  const zone =
    document
      .querySelector(
        '#open-account-zone'
      )
      ?.value
      .trim();

  const customerName =
    document
      .querySelector(
        '#open-account-customer'
      )
      ?.value
      .trim()
    || 'Consumidor final';


  if (!label) {

    toast(
      'Ingresa el número o nombre de la mesa.'
    );

    return;
  }


  const button =
    document.querySelector(
      '#save-open-account'
    );

  button.disabled = true;
  button.textContent =
    'Abriendo...';


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/open-accounts`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify({
              account_type:
                accountType,

              label,

              zone:
                zone || null,

              customer_name:
                customerName
            })
        }
      );


    if (!response.ok) {

      let detail =
        'No fue posible abrir la cuenta.';

      try {
        const error =
          await response.json();

        detail =
          error.detail
          || detail;

      } catch { }

      throw new Error(
        detail
      );
    }


    const account =
      await response.json();


    closeOpenAccountModal();


    await syncFromApi(
      false
    );


    render(
      'sales'
    );


    toast(
      `${account.account_type} ${account.label} abierta correctamente.`
    );


  } catch (error) {

    toast(
      error.message
    );

    button.disabled = false;

    button.textContent =
      'Abrir cuenta';
  }
}


/* ------------------------------------------------------------
   AGREGAR CONSUMO
------------------------------------------------------------ */

function openAccountConsumptionModal(
  accountId
) {

  const account =
    (state.openAccounts || [])
      .find(
        item =>
          Number(item.id)
          === Number(accountId)
      );


  if (!account) {

    toast(
      'Cuenta no encontrada.'
    );

    return;
  }


  document
    .querySelector(
      '#account-consumption-modal'
    )
    ?.remove();


  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="account-consumption-modal"
      >
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">
                ${account.account_type}
              </p>

              <h2>
                ${account.label}
              </h2>

              <small style="color:var(--muted)">
                ${account.number}
                · ${money(account.total)}
              </small>
            </div>

            <button
              class="icon-btn"
              id="close-account-consumption"
              type="button"
            >
              ×
            </button>
          </div>


          <div class="field full account-product-search-field">

            <label for="account-product-search">
              Buscar producto
            </label>

            <input
              id="account-product-search"
              type="search"
              placeholder="Nombre o SKU…"
              autocomplete="off"
            />

            <input
              id="account-product-id"
              type="hidden"
            />

            <div
              id="account-product-results"
              class="sale-product-results"
            ></div>

          </div>


          <div
            id="account-product-selected"
            class="sale-product-selected"
            hidden
          ></div>


          <label class="field" style="margin-top:14px">
            Cantidad

            <input
              id="account-product-quantity"
              type="number"
              min="1"
              step="1"
              value="1"
            />

            <div class="sale-quick-quantities">

              <button type="button" data-account-qty="1">
                1
              </button>

              <button type="button" data-account-qty="2">
                2
              </button>

              <button type="button" data-account-qty="4">
                4
              </button>

              <button type="button" data-account-qty="6">
                6
              </button>

              <button type="button" data-account-qty="12">
                12
              </button>

            </div>
          </label>


          <div class="modal-actions">

            <button
              class="btn secondary"
              id="cancel-account-consumption"
              type="button"
            >
              Cancelar
            </button>

            <button
              class="btn"
              id="save-account-consumption"
              type="button"
            >
              Agregar consumo
            </button>

          </div>

        </div>
      </div>
    `
  );


  initializeAccountProductSearch();


  document
    .querySelectorAll(
      '[data-account-qty]'
    )
    .forEach(
      button => {

        button.onclick = () => {

          const input =
            document.querySelector(
              '#account-product-quantity'
            );

          if (input) {
            input.value =
              button.dataset.accountQty;
          }
        };
      }
    );


  document
    .querySelector(
      '#close-account-consumption'
    )
    .onclick =
    closeAccountConsumptionModal;

  document
    .querySelector(
      '#cancel-account-consumption'
    )
    .onclick =
    closeAccountConsumptionModal;

  document
    .querySelector(
      '#save-account-consumption'
    )
    .onclick =
    () =>
      submitAccountConsumption(
        account.id
      );
}


function closeAccountConsumptionModal() {

  document
    .querySelector(
      '#account-consumption-modal'
    )
    ?.remove();
}


function initializeAccountProductSearch() {

  const input =
    document.querySelector(
      '#account-product-search'
    );

  if (!input) {
    return;
  }


  const renderResults =
    () => {

      const query =
        normalizeSaleSearch(
          input.value
        );


      const products =
        state.products
          .filter(
            product =>
              product.id != null
          )
          .filter(
            product => {

              if (!query) {
                return true;
              }

              const searchable =
                normalizeSaleSearch(
                  `${product.name || ''} ${product.sku || ''}`
                );

              return searchable.includes(
                query
              );
            }
          )
          .slice(
            0,
            8
          );


      const container =
        document.querySelector(
          '#account-product-results'
        );


      if (!container) {
        return;
      }


      if (!products.length) {

        container.innerHTML = `
          <div class="sale-product-no-results">
            No se encontraron productos.
          </div>
        `;

        return;
      }


      container.innerHTML =
        products.map(
          product => `
            <button
              type="button"
              class="sale-product-result"
              data-account-product-id="${product.id}"
              ${Number(product.stock) <= 0
              ? 'disabled'
              : ''
            }
            >
              <span class="sale-product-result-main">

                <strong>
                  ${product.name}
                </strong>

                <small>
                  ${product.sku || 'Sin SKU'}
                </small>

              </span>

              <span class="sale-product-result-meta">

                <strong>
                  ${money(product.price)}
                </strong>

                <small>
                  Stock:
                  ${Number(product.stock)}
                </small>

              </span>
            </button>
          `
        ).join('');


      container
        .querySelectorAll(
          '[data-account-product-id]'
        )
        .forEach(
          button => {

            button.onclick = () => {

              selectAccountProduct(
                Number(
                  button.dataset.accountProductId
                )
              );
            };
          }
        );
    };


  input.addEventListener(
    'input',
    renderResults
  );


  input.addEventListener(
    'focus',
    renderResults
  );


  renderResults();

  input.focus();
}


function selectAccountProduct(
  productId
) {

  const product =
    state.products.find(
      item =>
        Number(item.id)
        === Number(productId)
    );


  if (!product) {
    return;
  }


  const hidden =
    document.querySelector(
      '#account-product-id'
    );

  const search =
    document.querySelector(
      '#account-product-search'
    );

  const selected =
    document.querySelector(
      '#account-product-selected'
    );

  const results =
    document.querySelector(
      '#account-product-results'
    );


  hidden.value =
    String(product.id);


  search.value =
    product.name;


  selected.hidden =
    false;


  selected.innerHTML = `
    <div>
      <small>
        Producto seleccionado
      </small>

      <strong>
        ${product.name}
      </strong>

      <span>
        Stock ${Number(product.stock)}
        · ${money(product.price)}
      </span>
    </div>
  `;


  results.hidden =
    true;


  document
    .querySelector(
      '#account-product-quantity'
    )
    ?.focus();
}


async function submitAccountConsumption(
  accountId
) {

  const productId =
    Number(
      document
        .querySelector(
          '#account-product-id'
        )
        ?.value
    );

  const quantity =
    Number(
      document
        .querySelector(
          '#account-product-quantity'
        )
        ?.value
    );


  if (!productId) {

    toast(
      'Selecciona un producto.'
    );

    return;
  }


  if (
    !Number.isFinite(quantity)
    || quantity <= 0
  ) {

    toast(
      'Ingresa una cantidad válida.'
    );

    return;
  }


  const button =
    document.querySelector(
      '#save-account-consumption'
    );

  button.disabled = true;
  button.textContent =
    'Agregando...';


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/open-accounts/${accountId}/items`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify({
              product_id:
                productId,

              quantity
            })
        }
      );


    if (!response.ok) {

      let detail =
        'No fue posible agregar el consumo.';

      try {
        const error =
          await response.json();

        detail =
          error.detail
          || detail;

      } catch { }

      throw new Error(
        detail
      );
    }


    closeAccountConsumptionModal();


    await syncFromApi(
      false
    );


    render(
      'sales'
    );


    toast(
      'Consumo agregado correctamente.'
    );


  } catch (error) {

    toast(
      error.message
    );

    button.disabled = false;
    button.textContent =
      'Agregar consumo';
  }
}


/* ------------------------------------------------------------
   CERRAR CUENTA
------------------------------------------------------------ */

function openCloseAccountModal(
  accountId
) {

  const account =
    (state.openAccounts || [])
      .find(
        item =>
          Number(item.id)
          === Number(accountId)
      );


  if (!account) {

    toast(
      'Cuenta no encontrada.'
    );

    return;
  }


  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="close-account-modal"
      >
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">
                CERRAR CUENTA
              </p>

              <h2>
                ${account.account_type}
                ${account.label}
              </h2>
            </div>

            <span class="pill green">
              ${money(account.total)}
            </span>
          </div>


          <label class="field full">
            Método de pago

            <select id="close-account-payment">
              <option value="efectivo">
                Efectivo
              </option>

              <option value="tarjeta">
                Tarjeta
              </option>

              <option value="transferencia">
                Transferencia
              </option>

              <option value="qr">
                QR
              </option>
            </select>
          </label>


          <div class="modal-actions">

            <button
              class="btn secondary"
              id="cancel-close-account"
              type="button"
            >
              Cancelar
            </button>

            <button
              class="btn"
              id="confirm-close-account"
              type="button"
            >
              Cerrar y cobrar
            </button>

          </div>

        </div>
      </div>
    `
  );


  document
    .querySelector(
      '#cancel-close-account'
    )
    .onclick =
    closeCloseAccountModal;


  document
    .querySelector(
      '#confirm-close-account'
    )
    .onclick =
    () =>
      submitCloseAccount(
        account.id
      );
}


function closeCloseAccountModal() {

  document
    .querySelector(
      '#close-account-modal'
    )
    ?.remove();
}


async function submitCloseAccount(
  accountId
) {

  const paymentMethod =
    document
      .querySelector(
        '#close-account-payment'
      )
      ?.value;


  const button =
    document.querySelector(
      '#confirm-close-account'
    );


  button.disabled = true;

  button.textContent =
    'Cerrando...';


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/open-accounts/${accountId}/close`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify({
              payment_method:
                paymentMethod
            })
        }
      );


    if (!response.ok) {

      let detail =
        'No fue posible cerrar la cuenta.';

      try {
        const error =
          await response.json();

        detail =
          error.detail
          || detail;

      } catch { }


      throw new Error(
        detail
      );
    }


    const result =
      await response.json();


    closeCloseAccountModal();


    await syncFromApi(
      false
    );


    render(
      'sales'
    );


    toast(
      `${result.sale.number} registrada por ${money(result.sale.total)}`
    );


  } catch (error) {

    toast(
      error.message
    );

    button.disabled = false;

    button.textContent =
      'Cerrar y cobrar';
  }
}


/* ============================================================
   SALE MODAL
============================================================ */

let saleDraft = [];

function openSaleModal() {
  const realProducts = state.products.filter(p => p.id != null);

  if (!realProducts.length) {
    toast('La API no tiene productos disponibles.');
    return;
  }

  saleDraft = [];

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="sale-modal">
        <div class="modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">VENTA</p>
              <h2>Nueva venta</h2>
            </div>

            <button class="icon-btn" id="close-sale-modal">×</button>
          </div>

          <div class="form-grid">

            <label class="field full">
              Cliente
              <input
                id="sale-customer"
                value="Consumidor final"
                maxlength="160"
              />
            </label>

            <div class="field full sale-product-search-field">
              <label for="sale-product-search">
                Producto
              </label>

              <div class="sale-product-search-box">
                <span class="sale-product-search-icon">
                  ⌕
                </span>

                <input
                  id="sale-product-search"
                  type="search"
                  placeholder="Buscar por nombre o SKU…"
                  autocomplete="off"
                  spellcheck="false"
                />

                <input
                  id="sale-product"
                  type="hidden"
                  value=""
                />
              </div>

              <div
                id="sale-favorites"
                class="sale-favorites"
              ></div>

              <div
                id="sale-product-results"
                class="sale-product-results"
              ></div>

              <div
                id="sale-product-selected"
                class="sale-product-selected"
                hidden
              ></div>
            </div>

            <label class="field">
              Cantidad

              <input
                id="sale-quantity"
                type="number"
                min="1"
                step="1"
                value="1"
              />

              <div class="sale-quick-quantities">
                <button type="button" data-sale-qty="1">1</button>
                <button type="button" data-sale-qty="2">2</button>
                <button type="button" data-sale-qty="4">4</button>
                <button type="button" data-sale-qty="6">6</button>
                <button type="button" data-sale-qty="12">12</button>
              </div>
            </label>

            <div class="field full">
              <button class="btn secondary" id="add-sale-item">
                + Agregar producto
              </button>
            </div>

            <label class="field full">
              Método de pago
              <select id="sale-payment">
                <option value="efectivo">Efectivo</option>
                <option value="tarjeta">Tarjeta</option>
                <option value="transferencia">Transferencia</option>
                <option value="qr">QR</option>
              </select>
            </label>

          </div>

          <div id="sale-cart"></div>

          <div class="modal-actions">
            <button class="btn secondary" id="cancel-sale">
              Cancelar
            </button>

            <button class="btn" id="confirm-sale">
              Confirmar venta
            </button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-sale-modal').onclick = closeSaleModal;
  document.querySelector('#cancel-sale').onclick = closeSaleModal;
  document.querySelector('#add-sale-item').onclick = addSaleItem;
  document.querySelector('#confirm-sale').onclick = submitSale;

  initializeSaleProductSearch();

  renderSaleFavorites();

  document
    .querySelectorAll(
      '[data-sale-qty]'
    )
    .forEach(
      button => {

        button.onclick = () => {
          setSaleQuantity(
            button.dataset.saleQty
          );
        };
      }
    );

  document.querySelector('#sale-modal').addEventListener('click', event => {
    if (event.target.id === 'sale-modal') {
      closeSaleModal();
    }
  });

  refreshSaleCart();
}


function closeSaleModal() {
  document.querySelector('#sale-modal')?.remove();
  saleDraft = [];
}



const SALE_FAVORITES_KEY =
  'lp-sale-favorites';

const LAST_SALE_KEY =
  'lp-last-sale';


function getSaleFavoriteIds() {

  try {
    return JSON.parse(
      localStorage.getItem(
        SALE_FAVORITES_KEY
      ) || '[]'
    )
      .map(Number)
      .filter(Boolean);

  } catch {
    return [];
  }
}


function saveSaleFavoriteIds(ids) {

  localStorage.setItem(
    SALE_FAVORITES_KEY,
    JSON.stringify(
      [...new Set(ids.map(Number))]
    )
  );
}


function toggleSaleFavorite(productId) {

  productId =
    Number(productId);

  let ids =
    getSaleFavoriteIds();

  if (ids.includes(productId)) {
    ids =
      ids.filter(
        id => id !== productId
      );
  } else {
    ids.push(productId);
  }

  saveSaleFavoriteIds(ids);

  renderSaleFavorites();

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  renderSaleProductResults(
    search?.value || ''
  );
}


function renderSaleFavorites() {

  const container =
    document.querySelector(
      '#sale-favorites'
    );

  if (!container) {
    return;
  }

  const favoriteIds =
    getSaleFavoriteIds();

  const products =
    favoriteIds
      .map(
        id =>
          state.products.find(
            product =>
              Number(product.id) === id
          )
      )
      .filter(Boolean)
      .slice(0, 8);

  if (!products.length) {

    container.innerHTML = `
      <div class="sale-favorites-empty">
        ☆ Marca productos como favoritos para
        tenerlos siempre a un clic.
      </div>
    `;

    return;
  }

  container.innerHTML = `
    <div class="sale-favorites-title">
      <span>Favoritos</span>
      <small>Acceso rápido</small>
    </div>

    <div class="sale-favorites-grid">
      ${products.map(
    product => `
          <button
            type="button"
            class="sale-favorite-product"
            data-favorite-product-id="${product.id}"
            ${Number(product.stock) <= 0
        ? 'disabled'
        : ''
      }
          >
            <strong>
              ${product.name}
            </strong>

            <small>
              ${money(product.price)}
              · stock ${Number(product.stock)}
            </small>
          </button>
        `
  ).join('')}
    </div>
  `;

  container
    .querySelectorAll(
      '[data-favorite-product-id]'
    )
    .forEach(
      button => {

        button.onclick = () => {

          selectSaleProduct(
            Number(
              button.dataset.favoriteProductId
            )
          );
        };
      }
    );
}


function setSaleQuantity(quantity) {

  const input =
    document.querySelector(
      '#sale-quantity'
    );

  if (!input) {
    return;
  }

  input.value =
    Math.max(
      1,
      Number(quantity) || 1
    );
}


function adjustSaleItemQuantity(
  productId,
  delta
) {

  const item =
    saleDraft.find(
      saleItem =>
        Number(saleItem.product_id)
        === Number(productId)
    );

  if (!item) {
    return;
  }

  const nextQuantity =
    Number(item.quantity)
    + Number(delta);

  if (nextQuantity <= 0) {

    removeSaleItem(
      Number(productId)
    );

    return;
  }

  if (
    nextQuantity
    > Number(item.stock)
  ) {
    toast(
      `Stock insuficiente para ${item.name}.`
    );

    return;
  }

  item.quantity =
    nextQuantity;

  refreshSaleCart();
}


function saveLastSaleDraft() {

  if (!saleDraft.length) {
    return;
  }

  localStorage.setItem(
    LAST_SALE_KEY,
    JSON.stringify(
      saleDraft.map(
        item => ({
          product_id:
            Number(item.product_id),

          quantity:
            Number(item.quantity)
        })
      )
    )
  );
}


function repeatLastSale() {

  let saved = [];

  try {
    saved =
      JSON.parse(
        localStorage.getItem(
          LAST_SALE_KEY
        ) || '[]'
      );
  } catch {
    saved = [];
  }

  if (!saved.length) {

    toast(
      'Todavía no hay una venta anterior para repetir.'
    );

    return;
  }

  openSaleModal();

  saleDraft = [];

  saved.forEach(
    savedItem => {

      const product =
        state.products.find(
          item =>
            Number(item.id)
            === Number(savedItem.product_id)
        );

      if (!product) {
        return;
      }

      const quantity =
        Math.min(
          Number(savedItem.quantity) || 1,
          Number(product.stock) || 0
        );

      if (quantity <= 0) {
        return;
      }

      saleDraft.push({
        product_id:
          Number(product.id),

        quantity,

        name:
          product.name,

        unit_price:
          Number(product.price),

        stock:
          Number(product.stock)
      });
    }
  );

  refreshSaleCart();

  if (!saleDraft.length) {
    toast(
      'Los productos de la última venta ya no tienen stock.'
    );
  }
}


function normalizeSaleSearch(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}


function getSaleSearchProducts(query = '') {

  const normalizedQuery =
    normalizeSaleSearch(query);

  const products =
    state.products
      .filter(
        product =>
          product.id != null
      )
      .filter(
        product => {
          if (!normalizedQuery) {
            return true;
          }

          const searchable =
            normalizeSaleSearch(
              `${product.name || ''} ${product.sku || ''}`
            );

          return searchable.includes(
            normalizedQuery
          );
        }
      )
      .sort(
        (a, b) => {

          const aName =
            normalizeSaleSearch(
              a.name
            );

          const bName =
            normalizeSaleSearch(
              b.name
            );

          if (normalizedQuery) {

            const aStarts =
              aName.startsWith(
                normalizedQuery
              );

            const bStarts =
              bName.startsWith(
                normalizedQuery
              );

            if (
              aStarts
              && !bStarts
            ) {
              return -1;
            }

            if (
              !aStarts
              && bStarts
            ) {
              return 1;
            }
          }

          return aName.localeCompare(
            bName
          );
        }
      );

  return products.slice(
    0,
    8
  );
}


function renderSaleProductResults(
  query = ''
) {

  const container =
    document.querySelector(
      '#sale-product-results'
    );

  if (!container) {
    return;
  }

  const products =
    getSaleSearchProducts(
      query
    );

  if (!products.length) {

    container.innerHTML = `
      <div class="sale-product-no-results">
        No se encontraron productos.
      </div>
    `;

    container.hidden = false;

    return;
  }

  container.innerHTML =
    products.map(
      product => {

        const stock =
          Number(
            product.stock || 0
          );

        const disabled =
          stock <= 0;

        return `
          <button
            type="button"
            class="sale-product-result ${disabled
            ? 'is-out-of-stock'
            : ''
          }"
            data-sale-product-id="${product.id}"
            ${disabled
            ? 'disabled'
            : ''
          }
          >
            <span class="sale-product-result-main">
              <strong>
                ${product.name}
              </strong>

              <small>
                ${product.sku
            ? `SKU ${product.sku}`
            : 'Sin SKU'
          }
              </small>
            </span>

            <span class="sale-product-result-meta">
              <span
                class="sale-toggle-favorite"
                data-toggle-sale-favorite="${product.id}"
                title="Favorito"
              >
                ${getSaleFavoriteIds().includes(Number(product.id))
            ? '★'
            : '☆'
          }
              </span>
              <strong>
                ${money(product.price)}
              </strong>

              <small class="${stock <= 0
            ? 'stock-empty'
            : ''
          }">
                ${stock > 0
            ? `Stock: ${stock}`
            : 'Sin stock'
          }
              </small>
            </span>
          </button>
        `;
      }
    ).join('');

  container.hidden = false;

  container
    .querySelectorAll(
      '[data-toggle-sale-favorite]'
    )
    .forEach(
      favorite => {

        favorite.onclick = event => {
          event.preventDefault();
          event.stopPropagation();

          toggleSaleFavorite(
            Number(
              favorite.dataset.toggleSaleFavorite
            )
          );
        };
      }
    );


  container
    .querySelectorAll(
      '[data-sale-product-id]'
    )
    .forEach(
      button => {

        button.onclick = () => {

          selectSaleProduct(
            Number(
              button.dataset.saleProductId
            )
          );
        };
      }
    );
}


function selectSaleProduct(
  productId
) {

  const product =
    state.products.find(
      item =>
        Number(item.id)
        === Number(productId)
    );

  if (!product) {
    return;
  }

  const hidden =
    document.querySelector(
      '#sale-product'
    );

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  const selected =
    document.querySelector(
      '#sale-product-selected'
    );

  const results =
    document.querySelector(
      '#sale-product-results'
    );

  if (hidden) {
    hidden.value =
      String(product.id);
  }

  if (search) {
    search.value =
      product.name;
  }

  if (selected) {

    selected.hidden = false;

    selected.innerHTML = `
      <div>
        <small>
          Producto seleccionado
        </small>

        <strong>
          ${product.name}
        </strong>

        <span>
          ${product.sku
        ? `SKU ${product.sku} · `
        : ''
      }
          Stock ${Number(product.stock)}
        </span>
      </div>

      <strong class="sale-selected-price">
        ${money(product.price)}
      </strong>
    `;
  }

  if (results) {
    results.hidden = true;
  }

  document
    .querySelector(
      '#sale-quantity'
    )
    ?.focus();
}


function clearSaleProductSelection() {

  const hidden =
    document.querySelector(
      '#sale-product'
    );

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  const selected =
    document.querySelector(
      '#sale-product-selected'
    );

  if (hidden) {
    hidden.value = '';
  }

  if (search) {
    search.value = '';
  }

  if (selected) {
    selected.hidden = true;
    selected.innerHTML = '';
  }
}


function initializeSaleProductSearch() {

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  const hidden =
    document.querySelector(
      '#sale-product'
    );

  const results =
    document.querySelector(
      '#sale-product-results'
    );

  if (
    !search
    || !hidden
    || !results
  ) {
    return;
  }

  search.addEventListener(
    'focus',
    () => {
      renderSaleProductResults(
        search.value
      );
    }
  );

  search.addEventListener(
    'input',
    () => {

      hidden.value = '';

      const selected =
        document.querySelector(
          '#sale-product-selected'
        );

      if (selected) {
        selected.hidden = true;
      }

      renderSaleProductResults(
        search.value
      );
    }
  );

  search.addEventListener(
    'keydown',
    event => {

      if (
        event.key !== 'Enter'
      ) {
        return;
      }

      event.preventDefault();

      const firstAvailable =
        document.querySelector(
          '#sale-product-results ' +
          '[data-sale-product-id]:not(:disabled)'
        );

      if (firstAvailable) {

        selectSaleProduct(
          Number(
            firstAvailable.dataset.saleProductId
          )
        );
      }
    }
  );

  setTimeout(
    () => {
      search.focus();
      renderSaleProductResults('');
    },
    0
  );
}


function addSaleItem() {
  const productId = Number(
    document.querySelector(
      '#sale-product'
    )?.value
  );

  if (!productId) {
    toast(
      'Busca y selecciona un producto.'
    );

    document
      .querySelector(
        '#sale-product-search'
      )
      ?.focus();

    return;
  }

  const quantity = Number(
    document.querySelector('#sale-quantity').value
  );

  if (!Number.isFinite(quantity) || quantity <= 0) {
    toast('Ingresa una cantidad válida.');
    return;
  }

  const product = state.products.find(
    p => Number(p.id) === productId
  );

  if (!product) {
    toast('Producto no encontrado.');
    return;
  }

  const existing = saleDraft.find(
    item => item.product_id === productId
  );

  const currentQuantity = existing
    ? existing.quantity
    : 0;

  if (currentQuantity + quantity > Number(product.stock)) {
    toast(`Stock insuficiente para ${product.name}.`);
    return;
  }

  if (existing) {
    existing.quantity += quantity;
  } else {
    saleDraft.push({
      product_id: productId,
      quantity,
      name: product.name,
      unit_price: Number(product.price),
      stock: Number(product.stock)
    });
  }

  document.querySelector('#sale-quantity').value = 1;

  clearSaleProductSelection();

  refreshSaleCart();

  setTimeout(
    () => {
      const search =
        document.querySelector(
          '#sale-product-search'
        );

      if (search) {
        search.focus();
        renderSaleProductResults('');
      }
    },
    0
  );
}


function removeSaleItem(productId) {
  saleDraft = saleDraft.filter(
    item => item.product_id !== productId
  );

  refreshSaleCart();
}


function refreshSaleCart() {
  const container = document.querySelector('#sale-cart');

  if (!container) return;

  if (!saleDraft.length) {
    container.innerHTML = `
      <div class="empty sale-empty">
        Agrega al menos un producto.
      </div>
    `;
    return;
  }

  const total = saleDraft.reduce(
    (acc, item) =>
      acc + item.quantity * item.unit_price,
    0
  );

  container.innerHTML = `
    <div class="sale-cart">
      <table class="table">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Cant.</th>
            <th>Precio</th>
            <th>Subtotal</th>
            <th></th>
          </tr>
        </thead>

        <tbody>
          ${saleDraft.map(item => `
            <tr>
              <td>${item.name}</td>
              <td>
                <div class="sale-cart-quantity">
                  <button
                    type="button"
                    class="sale-qty-minus"
                    data-product-id="${item.product_id}"
                  >
                    −
                  </button>

                  <strong>
                    ${item.quantity}
                  </strong>

                  <button
                    type="button"
                    class="sale-qty-plus"
                    data-product-id="${item.product_id}"
                    ${Number(item.quantity) >= Number(item.stock)
      ? 'disabled'
      : ''
    }
                  >
                    +
                  </button>
                </div>

                <small class="sale-stock-after">
                  Quedan:
                  ${Math.max(
      0,
      Number(item.stock)
      - Number(item.quantity)
    )}
                </small>
              </td>
              <td>${money(item.unit_price)}</td>
              <td>
                <strong>
                  ${money(item.quantity * item.unit_price)}
                </strong>
              </td>
              <td>
                <button
                  class="remove-item"
                  data-product-id="${item.product_id}"
                >
                  ×
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>

      <div class="sale-total">
        <span>Total</span>
        <strong>${money(total)}</strong>
      </div>
    </div>
  `;

  container
    .querySelectorAll(
      '.sale-qty-minus'
    )
    .forEach(
      button => {
        button.onclick = () =>
          adjustSaleItemQuantity(
            Number(
              button.dataset.productId
            ),
            -1
          );
      }
    );

  container
    .querySelectorAll(
      '.sale-qty-plus'
    )
    .forEach(
      button => {
        button.onclick = () =>
          adjustSaleItemQuantity(
            Number(
              button.dataset.productId
            ),
            1
          );
      }
    );


  container
    .querySelectorAll('.remove-item')
    .forEach(button => {
      button.onclick = () =>
        removeSaleItem(
          Number(button.dataset.productId)
        );
    });
}


async function submitSale() {
  if (!saleDraft.length) {
    toast('Agrega productos a la venta.');
    return;
  }

  const button = document.querySelector('#confirm-sale');

  button.disabled = true;
  button.textContent = 'Registrando...';

  saveLastSaleDraft();

  const payload = {
    customer_name:
      document.querySelector('#sale-customer').value.trim()
      || 'Consumidor final',

    payment_method:
      document.querySelector('#sale-payment').value,

    items: saleDraft.map(item => ({
      product_id: item.product_id,
      quantity: item.quantity
    }))
  };

  try {
    const response = await authenticatedFetch(`${API_BASE}/api/sales`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      let detail = 'No fue posible registrar la venta.';

      try {
        const error = await response.json();
        detail = error.detail || detail;
      } catch { }

      throw new Error(detail);
    }

    const result = await response.json();

    closeSaleModal();

    await syncFromApi(false);

    render('sales');

    toast(
      `Venta ${result.number} registrada por ${money(result.total)}`
    );

  } catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Confirmar venta';
  }
}




/* ============================================================
   EDIT PRODUCT MODAL
============================================================ */

function openEditProductModal(
  productId
) {

  if (
    state.currentUser?.role !== 'ADMIN'
  ) {
    toast(
      'Solo un administrador puede editar productos.'
    );

    return;
  }

  const product =
    state.products.find(
      item =>
        Number(item.id)
        === Number(productId)
    );

  if (!product) {
    toast(
      'Producto no encontrado.'
    );

    return;
  }

  document
    .querySelector(
      '#edit-product-modal'
    )
    ?.remove();

  const units = [
    'unidad',
    'botella',
    'caja',
    'paquete',
    'bolsa'
  ];

  if (
    product.unit
    && !units.includes(product.unit)
  ) {
    units.unshift(
      product.unit
    );
  }

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="edit-product-modal"
      >
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">
                INVENTARIO
              </p>

              <h2>
                Editar producto
              </h2>
            </div>

            <button
              class="icon-btn"
              id="close-edit-product-modal"
              type="button"
            >
              ×
            </button>
          </div>


          <div class="edit-product-stock-notice">
            <div>
              <small>
                Existencia actual
              </small>

              <strong>
                ${Number(product.stock)}
                ${product.unit || 'unidad'}
              </strong>
            </div>

            <span class="pill">
              Solo lectura
            </span>
          </div>

          <p class="edit-product-stock-help">
            Para modificar existencias utiliza
            <strong>Registrar movimiento</strong>.
            Así el sistema conserva la trazabilidad
            del inventario.
          </p>

          <div class="edit-product-image-section">
            <label class="eyebrow" style="margin-bottom:8px;display:block;">
              IMAGEN DEL PRODUCTO
            </label>

            <div class="product-image-upload-area" id="product-image-upload-area">
              <div class="product-image-preview" id="product-image-preview">
                ${product.image_url
      ? `<img src="${product.image_url}" alt="${product.name}" />`
      : `<span class="product-image-placeholder">Sin imagen</span>`
    }
              </div>

              <div class="product-image-actions">
                <label class="btn secondary" style="cursor:pointer;">
                  ${product.image_url ? 'Cambiar imagen' : 'Subir imagen'}
                  <input
                    type="file"
                    id="product-image-input"
                    accept=".jpg,.jpeg,.png,.webp"
                    style="display:none;"
                  />
                </label>

                ${product.image_url
      ? `<button
                      type="button"
                      class="btn secondary"
                      id="product-image-remove"
                    >
                      Eliminar imagen
                    </button>`
      : ''
    }
              </div>

              <small class="product-image-help">
                JPG, PNG o WebP. Máximo 5 MB.
              </small>
            </div>
          </div>

          <div class="form-grid">

            <label class="field full">
              Nombre

              <input
                id="edit-product-name"
                maxlength="160"
                value="${String(product.name || '')
      .replace(/"/g, '&quot;')}"
              />
            </label>


            <label class="field">
              SKU

              <input
                id="edit-product-sku"
                maxlength="60"
                value="${String(product.sku || '')
      .replace(/"/g, '&quot;')}"
                placeholder="Ej. LIC-WHI-001"
              />
            </label>


            <label class="field">
              Unidad

              <select id="edit-product-unit">
                ${units.map(
        unit => `
                    <option
                      value="${unit}"
                      ${unit === product.unit
            ? 'selected'
            : ''
          }
                    >
                      ${unit.charAt(0).toUpperCase()
          + unit.slice(1)}
                    </option>
                  `
      ).join('')}
              </select>
            </label>


            <label class="field">
              Precio de venta

              <input
                id="edit-product-price"
                type="number"
                min="0"
                step="100"
                value="${Number(product.price || 0)}"
              />
            </label>


            <label class="field">
              Avisarme cuando queden

              <input
                id="edit-product-minimum-stock"
                type="number"
                min="0"
                step="1"
                value="${Number(
        product.minimum_stock || 0
      )}"
              />
            </label>

          </div>


          <div class="modal-actions">

            <button
              class="btn secondary"
              id="cancel-edit-product"
              type="button"
            >
              Cancelar
            </button>

            <button
              class="btn"
              id="save-edit-product"
              type="button"
            >
              Guardar cambios
            </button>

          </div>

        </div>
      </div>
    `
  );


  document
    .querySelector(
      '#close-edit-product-modal'
    )
    .onclick =
    closeEditProductModal;

  document
    .querySelector(
      '#cancel-edit-product'
    )
    .onclick =
    closeEditProductModal;

  document
    .querySelector(
      '#save-edit-product'
    )
    .onclick =
    () => saveEditProduct(
      product.id
    );


  document
    .querySelector(
      '#edit-product-modal'
    )
    .addEventListener(
      'click',
      event => {

        if (
          event.target.id
          === 'edit-product-modal'
        ) {
          closeEditProductModal();
        }
      }
    );


  setTimeout(
    () => {
      document
        .querySelector(
          '#edit-product-name'
        )
        ?.focus();
    },
    0
  );

  let pendingImageFile = null;

  const imageInput = document.querySelector('#product-image-input');
  const imagePreview = document.querySelector('#product-image-preview');
  const imageRemoveBtn = document.querySelector('#product-image-remove');

  if (imageInput) {
    imageInput.addEventListener('change', event => {
      const file = event.target.files?.[0];
      if (!file) return;

      const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
      if (!allowedTypes.includes(file.type)) {
        toast('Tipo de archivo no permitido. Usa JPG, PNG o WebP.');
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        toast('El archivo excede el tamaño máximo de 5 MB.');
        return;
      }

      pendingImageFile = file;

      const reader = new FileReader();
      reader.onload = e => {
        if (imagePreview) {
          imagePreview.innerHTML =
            `<img src="${e.target.result}" alt="Preview" />`;
        }
      };
      reader.readAsDataURL(file);
    });
  }

  if (imageRemoveBtn) {
    imageRemoveBtn.addEventListener('click', async () => {
      pendingImageFile = 'REMOVE';

      if (imagePreview) {
        imagePreview.innerHTML =
          `<span class="product-image-placeholder">Sin imagen</span>`;
      }

      imageRemoveBtn.remove();

      const uploadLabel = document.querySelector('.product-image-actions label');
      if (uploadLabel) {
        uploadLabel.textContent = 'Subir imagen';
      }
    });
  }

  window._pendingProductImage = null;
  Object.defineProperty(window, '_pendingProductImage', {
    get: () => pendingImageFile,
    configurable: true,
  });
}


function closeEditProductModal() {

  document
    .querySelector(
      '#edit-product-modal'
    )
    ?.remove();
}


async function saveEditProduct(
  productId
) {

  if (
    state.currentUser?.role !== 'ADMIN'
  ) {
    toast(
      'Solo un administrador puede editar productos.'
    );

    return;
  }


  const name =
    document
      .querySelector(
        '#edit-product-name'
      )
      ?.value
      .trim();

  const sku =
    document
      .querySelector(
        '#edit-product-sku'
      )
      ?.value
      .trim();

  const unit =
    document
      .querySelector(
        '#edit-product-unit'
      )
      ?.value
      .trim();

  const price =
    Number(
      document
        .querySelector(
          '#edit-product-price'
        )
        ?.value
    );

  const minimumStock =
    Number(
      document
        .querySelector(
          '#edit-product-minimum-stock'
        )
        ?.value
    );


  if (
    !name
    || name.length < 2
  ) {
    toast(
      'Ingresa un nombre válido.'
    );

    return;
  }


  if (
    !Number.isFinite(price)
    || price < 0
  ) {
    toast(
      'Ingresa un precio válido.'
    );

    return;
  }


  if (
    !Number.isFinite(minimumStock)
    || minimumStock < 0
  ) {
    toast(
      'Ingresa un stock mínimo válido.'
    );

    return;
  }


  const button =
    document.querySelector(
      '#save-edit-product'
    );

  button.disabled = true;
  button.textContent =
    'Guardando...';


  try {

    const response =
      await adminFetch(
        `${API_BASE}/api/products/${productId}`,
        {
          method: 'PATCH',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify({
              name,
              sku: sku || null,
              unit,
              price,
              minimum_stock:
                minimumStock
            })
        }
      );


    if (!response.ok) {

      let detail =
        'No fue posible actualizar el producto.';

      try {
        const error =
          await response.json();

        detail =
          error.detail
          || detail;

      } catch { }

      throw new Error(
        detail
      );
    }


    const updated =
      await response.json();


    const pendingImage = window._pendingProductImage;

    if (pendingImage === 'REMOVE') {
      try {
        await adminFetch(
          `${API_BASE}/api/products/${productId}/image`,
          { method: 'DELETE' }
        );
      } catch { }
    } else if (pendingImage instanceof File) {
      try {
        const formData = new FormData();
        formData.append('file', pendingImage);

        await adminFetch(
          `${API_BASE}/api/products/${productId}/image`,
          {
            method: 'POST',
            body: formData,
          }
        );
      } catch { }
    }

    window._pendingProductImage = null;

    closeEditProductModal();


    currentView =
      'inventory';


    await syncFromApi(
      false
    );


    toast(
      `${updated.name} actualizado correctamente.`
    );


  } catch (error) {

    toast(
      error.message
    );

    button.disabled = false;

    button.textContent =
      'Guardar cambios';
  }
}


/* ============================================================
   PRODUCT MODAL
============================================================ */

function openProductModal() {
  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="product-modal">
        <div class="modal">
          <div class="card-head">
            <div>
              <p class="eyebrow">INVENTARIO</p>
              <h2>Agregar producto</h2>
            </div>

            <button class="icon-btn" id="close-product-modal">×</button>
          </div>

          <div class="form-grid">
            <label class="field full">
              Nombre
              <input id="product-name" maxlength="160" placeholder="Ej. Whisky Old Parr 750ml" />
            </label>

            <label class="field">
              SKU
              <input id="product-sku" maxlength="60" placeholder="Ej. WOP-001" />
            </label>

            <label class="field">
              Unidad
              <select id="product-unit">
                <option value="unidad">Unidad</option>
                <option value="botella">Botella</option>
                <option value="caja">Caja</option>
                <option value="paquete">Paquete</option>
              </select>
            </label>

            <label class="field">
              Precio de venta
              <input id="product-price" type="number" min="0" step="100" value="0" />
            </label>

            <label class="field">
              Stock inicial
              <input id="product-stock" type="number" min="0" step="1" value="0" />
            </label>

            <label class="field full">
              Avisarme cuando queden

              <input
                id="product-minimum-stock"
                type="number"
                min="0"
                step="1"
                value="0"
              />

              <small style="color:var(--muted)">
                El sistema mostrará una alerta cuando
                el stock llegue a esta cantidad.
              </small>
            </label>
          </div>

          <div class="modal-actions">
            <button class="btn secondary" id="cancel-product">Cancelar</button>
            <button class="btn" id="save-product">Guardar producto</button>
          </div>
        </div>
      </div>
    `
  );

  document.querySelector('#close-product-modal').onclick = closeProductModal;
  document.querySelector('#cancel-product').onclick = closeProductModal;
  document.querySelector('#save-product').onclick = submitProduct;

  document.querySelector('#product-modal').addEventListener('click', event => {
    if (event.target.id === 'product-modal') {
      closeProductModal();
    }
  });

  document.querySelector('#product-name').focus();
}

function closeProductModal() {
  document.querySelector('#product-modal')?.remove();
}

async function submitProduct() {
  const name = document.querySelector('#product-name').value.trim();
  const sku = document.querySelector('#product-sku').value.trim();
  const unit = document.querySelector('#product-unit').value;
  const price = Number(document.querySelector('#product-price').value);
  const stock = Number(document.querySelector('#product-stock').value);
  const minimumStock = Number(
    document.querySelector('#product-minimum-stock').value
  );

  if (name.length < 2) {
    toast('Ingresa un nombre válido.');
    return;
  }

  if (price < 0 || stock < 0 || minimumStock < 0) {
    toast('Precio y existencias no pueden ser negativos.');
    return;
  }

  const button = document.querySelector('#save-product');

  button.disabled = true;
  button.textContent = 'Guardando...';

  const payload = {
    name,
    sku: sku || null,
    unit,
    price,
    stock,
    minimum_stock: minimumStock
  };

  try {
    const response = await adminFetch(`${API_BASE}/api/products`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let detail = 'No fue posible crear el producto.';

      try {
        const error = await response.json();
        detail = error.detail || detail;
      } catch { }

      throw new Error(
        typeof detail === 'string'
          ? detail
          : 'No fue posible crear el producto.'
      );
    }

    const product = await response.json();

    closeProductModal();

    await syncFromApi(false);

    render('inventory');

    toast(`Producto ${product.name} creado correctamente.`);
  } catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Guardar producto';
  }
}


/* ============================================================
   INVENTORY ADJUSTMENT MODAL
============================================================ */

function openInventoryAdjustmentModal() {
  const realProducts = state.products.filter(p => p.id != null);

  if (!realProducts.length) {
    toast('No hay productos disponibles.');
    return;
  }

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="adjustment-modal">
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">INVENTARIO</p>
              <h2>Registrar movimiento</h2>
            </div>

            <button class="icon-btn" id="close-adjustment-modal">×</button>
          </div>

          <div class="form-grid">

            <label class="field full">
              Producto
              <select id="adjustment-product">
                ${realProducts.map(p => `
                  <option value="${p.id}">
                    ${p.name} · stock actual ${Number(p.stock)}
                  </option>
                `).join('')}
              </select>
            </label>

            <label class="field">
              Tipo de movimiento
              <select id="adjustment-type">
                <option value="PURCHASE">Compra / reposición</option>
                <option value="ADJUSTMENT_IN">Ajuste positivo</option>
                <option value="ADJUSTMENT_OUT">Ajuste negativo</option>
                <option value="LOSS">Pérdida / merma</option>
              </select>
            </label>

            <label class="field">
              Cantidad
              <input
                id="adjustment-quantity"
                type="number"
                min="0.01"
                step="0.01"
                value="1"
              />
            </label>


            <label class="field full">
              Notas
              <input
                id="adjustment-notes"
                maxlength="250"
                placeholder="Ej. Compra proveedor Distribuciones La Patrona"
              />
            </label>

          </div>

          <div class="modal-actions">
            <button class="btn secondary" id="cancel-adjustment">
              Cancelar
            </button>

            <button class="btn" id="save-adjustment">
              Registrar movimiento
            </button>
          </div>

        </div>
      </div>
    `
  );

  document.querySelector('#close-adjustment-modal').onclick =
    closeInventoryAdjustmentModal;

  document.querySelector('#cancel-adjustment').onclick =
    closeInventoryAdjustmentModal;

  document.querySelector('#save-adjustment').onclick =
    submitInventoryAdjustment;

  document.querySelector('#adjustment-modal').addEventListener(
    'click',
    event => {
      if (event.target.id === 'adjustment-modal') {
        closeInventoryAdjustmentModal();
      }
    }
  );
}


function closeInventoryAdjustmentModal() {
  document.querySelector('#adjustment-modal')?.remove();
}


async function submitInventoryAdjustment() {
  const productId = Number(
    document.querySelector('#adjustment-product').value
  );

  const movementType =
    document.querySelector('#adjustment-type').value;

  const quantity = Number(
    document.querySelector('#adjustment-quantity').value
  );

  const notes =
    document.querySelector('#adjustment-notes').value.trim();

  if (!productId) {
    toast('Selecciona un producto.');
    return;
  }

  if (!Number.isFinite(quantity) || quantity <= 0) {
    toast('Ingresa una cantidad válida.');
    return;
  }

  const button = document.querySelector('#save-adjustment');

  button.disabled = true;
  button.textContent = 'Registrando...';

  const payload = {
    product_id: productId,
    movement_type: movementType,
    quantity,
    notes: notes || null
  };

  try {
    const response = await authenticatedFetch(`${API_BASE}/api/inventory/adjustments`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      let detail = 'No fue posible registrar el movimiento.';

      try {
        const error = await response.json();
        detail = error.detail || detail;
      } catch { }

      throw new Error(
        typeof detail === 'string'
          ? detail
          : 'No fue posible registrar el movimiento.'
      );
    }

    const result = await response.json();

    closeInventoryAdjustmentModal();

    await syncFromApi(false);

    render('inventory');

    const sign = Number(result.quantity) > 0 ? '+' : '';

    toast(
      `${result.product_name}: ${sign}${Number(result.quantity)} unidades`
    );

  } catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Registrar movimiento';
  }
}


/* ============================================================
   EXPENSE MODAL
============================================================ */

function openExpenseModal() {
  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div class="modal-overlay" id="expense-modal">
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">GASTOS</p>
              <h2>Registrar gasto</h2>
            </div>

            <button class="icon-btn" id="close-expense-modal">×</button>
          </div>

          <div class="form-grid">

            <label class="field full">
              Concepto
              <input
                id="expense-concept"
                maxlength="160"
                placeholder="Ej. Compra de hielo"
              />
            </label>

            <label class="field full">
              Proveedor
              <input
                id="expense-provider"
                maxlength="160"
                placeholder="Ej. Distribuciones La Patrona"
              />
            </label>

            <label class="field full">
              Valor
              <input
                id="expense-value"
                type="number"
                min="1"
                step="100"
                value="0"
              />
            </label>

            <label class="field full">
              Método de pago

              <select id="expense-payment-method">
                <option value="efectivo">Efectivo</option>
                <option value="transferencia">Transferencia</option>
                <option value="tarjeta">Tarjeta</option>
              </select>
            </label>

            <label class="field full">
              Notas
              <input
                id="expense-notes"
                maxlength="300"
                placeholder="Información adicional"
              />
            </label>

          </div>

          <div class="modal-actions">
            <button class="btn secondary" id="cancel-expense">
              Cancelar
            </button>

            <button class="btn" id="save-expense">
              Registrar gasto
            </button>
          </div>

        </div>
      </div>
    `
  );

  document.querySelector('#close-expense-modal').onclick =
    closeExpenseModal;

  document.querySelector('#cancel-expense').onclick =
    closeExpenseModal;

  document.querySelector('#save-expense').onclick =
    submitExpense;

  document.querySelector('#expense-modal').addEventListener(
    'click',
    event => {
      if (event.target.id === 'expense-modal') {
        closeExpenseModal();
      }
    }
  );

  document.querySelector('#expense-concept').focus();
}


function closeExpenseModal() {
  document.querySelector('#expense-modal')?.remove();
}


async function submitExpense() {
  const concept =
    document.querySelector('#expense-concept').value.trim();

  const provider =
    document.querySelector('#expense-provider').value.trim();

  const value = Number(
    document.querySelector('#expense-value').value
  );

  const paymentMethod =
    document.querySelector('#expense-payment-method').value;

  const notes =
    document.querySelector('#expense-notes').value.trim();

  if (concept.length < 2) {
    toast('Ingresa un concepto válido.');
    return;
  }

  if (!Number.isFinite(value) || value <= 0) {
    toast('Ingresa un valor válido.');
    return;
  }

  const button =
    document.querySelector('#save-expense');

  button.disabled = true;
  button.textContent = 'Registrando...';

  const payload = {
    concept,
    provider: provider || null,
    value,
    payment_method: paymentMethod,
    notes: notes || null
  };

  try {
    const response = await authenticatedFetch(`${API_BASE}/api/expenses`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      let detail =
        'No fue posible registrar el gasto.';

      try {
        const error = await response.json();
        detail = error.detail || detail;
      } catch { }

      throw new Error(
        typeof detail === 'string'
          ? detail
          : 'No fue posible registrar el gasto.'
      );
    }

    const expense = await response.json();

    closeExpenseModal();

    await syncFromApi(false);

    render('expenses');

    toast(
      `Gasto registrado por ${money(expense.value)}`
    );

  } catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Registrar gasto';
  }
}


/* ============================================================
   CASH REGISTER
============================================================ */

async function loadCashRegisterPanel() {
  const panel = document.querySelector('#cash-register-panel');

  if (!panel) {
    return;
  }

  try {
    const response = await fetch(
      `${API_BASE}/api/cash-register/current`
    );

    if (!response.ok) {
      throw new Error('No fue posible consultar la caja.');
    }

    const data = await response.json();

    if (data.status !== 'OPEN' || !data.session) {
      panel.innerHTML = `
        <div style="
          display:flex;
          justify-content:space-between;
          align-items:center;
          gap:20px;
          flex-wrap:wrap;
        ">
          <div>
            <span class="pill yellow">CAJA CERRADA</span>

            <p style="color:var(--muted);margin-top:10px">
              No hay una sesión de caja abierta.
            </p>
          </div>

          <button
            class="btn"
            onclick="openCashRegisterModal()"
          >
            Abrir caja
          </button>
        </div>
      `;

      return;
    }

    const session = data.session;

    panel.innerHTML = `
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:20px;
        flex-wrap:wrap;
        margin-bottom:20px;
      ">
        <div>
          <span class="pill green">CAJA ABIERTA</span>

          <p style="color:var(--muted);margin-top:10px">
            Apertura:
            ${new Date(session.opened_at).toLocaleString('es-CO')}
          </p>
        </div>

        <button
          class="btn secondary"
          onclick="openCashRegisterCloseModal()"
        >
          Cerrar caja
        </button>
      </div>

      <div
        class="grid"
        style="
          grid-template-columns:
          repeat(auto-fit,minmax(160px,1fr));
          gap:12px;
        "
      >
        <div class="card">
          <small>Monto inicial</small>
          <h2>${money(Number(session.opening_amount || 0))}</h2>
        </div>

        <div class="card">
          <small>Ventas en efectivo</small>
          <h2>${money(Number(session.cash_sales_total || 0))}</h2>
        </div>

        <div class="card">
          <small>Gastos</small>
          <h2>${money(Number(session.expenses_total || 0))}</h2>
        </div>

        <div class="card">
          <small>Efectivo esperado</small>
          <h2>${money(Number(session.expected_amount || 0))}</h2>
        </div>

        <div class="card">
          <small>Total vendido</small>
          <h2>${money(Number(session.sales_total || 0))}</h2>
        </div>
      </div>

      <div class="cash-payment-breakdown">
        ${Object.entries(
          session.payment_totals || {}
        ).map(([method,total]) => `
          <div>
            <span>${method}</span>
            <strong>${money(Number(total || 0))}</strong>
          </div>
        `).join('')}
      </div>
    `;
  }
  catch (error) {
    panel.innerHTML = `
      <p style="color:var(--muted)">
        ${error.message}
      </p>
    `;
  }
}


function closeCashModal(selector) {
  document.querySelector(selector)?.remove();
}


function openCashRegisterModal() {
  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="cash-open-modal"
      >
        <div class="modal">

          <div class="card-head">
            <div>
              <p class="eyebrow">CAJA</p>
              <h2>Abrir caja</h2>
            </div>

            <button
              class="icon-btn"
              onclick="closeCashModal('#cash-open-modal')"
            >
              ×
            </button>
          </div>

          <div class="form-grid">
            <label class="field full">
              Monto inicial

              <input
                id="cash-opening-amount"
                type="number"
                min="0"
                step="1000"
                value="0"
              />
            </label>
          </div>

          <div class="modal-actions">
            <button
              class="btn secondary"
              onclick="closeCashModal('#cash-open-modal')"
            >
              Cancelar
            </button>

            <button
              class="btn"
              id="confirm-cash-open"
              onclick="submitCashRegisterOpen()"
            >
              Abrir caja
            </button>
          </div>

        </div>
      </div>
    `
  );

  document
    .querySelector('#cash-opening-amount')
    ?.focus();
}


async function submitCashRegisterOpen() {
  const amount = Number(
    document.querySelector('#cash-opening-amount')?.value
  );

  if (!Number.isFinite(amount) || amount < 0) {
    toast('Ingresa un monto inicial válido.');
    return;
  }

  const button =
    document.querySelector('#confirm-cash-open');

  button.disabled = true;
  button.textContent = 'Abriendo...';

  try {
    const response = await authenticatedFetch(`${API_BASE}/api/cash-register/open`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          opening_amount: amount
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        'No fue posible abrir la caja.'
      );
    }

    closeCashModal('#cash-open-modal');

    await loadCashRegisterPanel();

    toast(`Caja abierta con ${money(amount)}`);
  }
  catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Abrir caja';
  }
}


async function openCashRegisterCloseModal() {
  try {
    const response = await fetch(
      `${API_BASE}/api/cash-register/current`
    );

    const data = await response.json();

    if (
      !response.ok ||
      data.status !== 'OPEN' ||
      !data.session
    ) {
      throw new Error('No hay una caja abierta.');
    }

    const session = data.session;

    document.body.insertAdjacentHTML(
      'beforeend',
      `
        <div
          class="modal-overlay"
          id="cash-close-modal"
        >
          <div class="modal">

            <div class="card-head">
              <div>
                <p class="eyebrow">CIERRE DE CAJA</p>
                <h2>Cerrar caja</h2>
              </div>

              <button
                class="icon-btn"
                onclick="closeCashModal('#cash-close-modal')"
              >
                ×
              </button>
            </div>

            <div class="form-grid">

              <div class="field full">
                <small>Efectivo esperado</small>

                <h2>
                  ${money(Number(session.expected_amount || 0))}
                </h2>
              </div>

              <label class="field full">
                Efectivo contado

                <input
                  id="cash-closing-amount"
                  type="number"
                  min="0"
                  step="1000"
                  placeholder="Ingresa el conteo real"
                />
              </label>

              <label class="field full">
                Observaciones del cierre

                <textarea
                  id="cash-closing-notes"
                  rows="3"
                  maxlength="500"
                  placeholder="Ej. diferencia revisada, efectivo entregado, novedad de turno..."
                ></textarea>
              </label>

            </div>

            <div class="modal-actions">

              <button
                class="btn secondary"
                onclick="closeCashModal('#cash-close-modal')"
              >
                Cancelar
              </button>

              <button
                class="btn"
                id="confirm-cash-close"
                onclick="submitCashRegisterClose()"
              >
                Cerrar caja
              </button>

            </div>

          </div>
        </div>
      `
    );

    document
      .querySelector('#cash-closing-amount')
      ?.focus();
  }
  catch (error) {
    toast(error.message);
  }
}


async function submitCashRegisterClose() {
  const amount = Number(
    document.querySelector('#cash-closing-amount')?.value
  );

  if (!Number.isFinite(amount) || amount < 0) {
    toast('Ingresa el efectivo contado.');
    return;
  }

  const button =
    document.querySelector('#confirm-cash-close');

  button.disabled = true;
  button.textContent = 'Cerrando...';

  try {
    const response = await authenticatedFetch(`${API_BASE}/api/cash-register/close`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          closing_amount: amount,
          notes:
            document
              .querySelector('#cash-closing-notes')
              ?.value
              ?.trim() || null
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        'No fue posible cerrar la caja.'
      );
    }

    closeCashModal('#cash-close-modal');

    await loadCashRegisterPanel();

    const difference =
      Number(data.difference || 0);

    if (difference === 0) {
      toast('Caja cerrada. Diferencia: $0');
    }
    else if (difference > 0) {
      toast(
        `Caja cerrada. Sobrante: ${money(difference)}`
      );
    }
    else {
      toast(
        `Caja cerrada. Faltante: ${money(Math.abs(difference))}`
      );
    }
  }
  catch (error) {
    toast(error.message);

    button.disabled = false;
    button.textContent = 'Cerrar caja';
  }
}

/* ============================================================
   VIEWS
============================================================ */


/* ============================================================
   PURCHASES / SUPPLIERS
============================================================ */

let purchaseDraft = [];


function purchaseEscape(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}


function purchaseDate(value) {
  if (!value) {
    return '—';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleString(
    'es-CO',
    {
      dateStyle: 'short',
      timeStyle: 'short'
    }
  );
}


async function loadPurchasesModuleData() {

  if (state.currentUser?.role !== 'ADMIN') {
    throw new Error(
      'Este módulo es exclusivo de administradores.'
    );
  }

  const [
    suppliersResponse,
    purchasesResponse
  ] = await Promise.all([
    authenticatedFetch(
      `${API_BASE}/api/suppliers`
    ),
    authenticatedFetch(
      `${API_BASE}/api/purchases`
    )
  ]);

  if (!suppliersResponse.ok) {
    const error =
      await suppliersResponse
        .json()
        .catch(() => ({}));

    throw new Error(
      error.detail ||
      'No fue posible cargar proveedores.'
    );
  }

  if (!purchasesResponse.ok) {
    const error =
      await purchasesResponse
        .json()
        .catch(() => ({}));

    throw new Error(
      error.detail ||
      'No fue posible cargar compras.'
    );
  }

  const suppliersData =
    await suppliersResponse.json();

  const purchasesData =
    await purchasesResponse.json();

  state.suppliers =
    Array.isArray(suppliersData?.suppliers)
      ? suppliersData.suppliers
      : [];

  state.purchases =
    Array.isArray(purchasesData?.purchases)
      ? purchasesData.purchases
      : [];
}


async function openPurchasesModule() {

  if (state.currentUser?.role !== 'ADMIN') {
    toast(
      'Este módulo es exclusivo de administradores.'
    );
    return;
  }

  try {

    await loadPurchasesModuleData();

    currentView = 'purchases';

    sessionStorage.setItem(
      'lp-current-view',
      'purchases'
    );

    render('purchases');

  }
  catch (error) {

    console.error(
      'Error cargando compras:',
      error
    );

    toast(
      error.message ||
      'No fue posible abrir Compras.'
    );
  }
}


function purchasesView() {

  const suppliers =
    state.suppliers || [];

  const purchases =
    state.purchases || [];

  const activeSuppliers =
    suppliers.filter(
      supplier => supplier.active
    );

  const totalPurchased =
    purchases.reduce(
      (sum, purchase) =>
        sum + Number(
          purchase.total || 0
        ),
      0
    );

  const lastPurchase =
    purchases[0] || null;


  const purchasesRows =
    purchases.length
      ? purchases.map(
          purchase => `
            <tr>
              <td>
                <strong>
                  ${purchaseEscape(
                    purchase.number
                  )}
                </strong>
              </td>

              <td>
                ${purchaseEscape(
                  purchase.supplier_name ||
                  'Sin proveedor'
                )}
              </td>

              <td>
                ${money(
                  purchase.total
                )}
              </td>

              <td>
                <span class="pill green">
                  ${purchaseEscape(
                    purchase.status
                  )}
                </span>
              </td>

              <td>
                ${purchaseDate(
                  purchase.created_at
                )}
              </td>

              <td>
                <button
                  type="button"
                  class="btn secondary purchase-detail-btn"
                  data-purchase-id="${purchase.id}"
                >
                  Ver detalle
                </button>
              </td>
            </tr>
          `
        ).join('')
      : `
          <tr>
            <td
              colspan="6"
              class="purchases-empty-cell"
            >
              Todavía no hay compras registradas.
            </td>
          </tr>
        `;


  const supplierRows =
    suppliers.length
      ? suppliers.map(
          supplier => `
            <tr>
              <td>
                <strong>
                  ${purchaseEscape(
                    supplier.name
                  )}
                </strong>
              </td>

              <td>
                ${purchaseEscape(
                  supplier.document || '—'
                )}
              </td>

              <td>
                ${purchaseEscape(
                  supplier.contact_name || '—'
                )}
              </td>

              <td>
                ${purchaseEscape(
                  supplier.phone || '—'
                )}
              </td>

              <td>
                <span
                  class="pill ${
                    supplier.active
                      ? 'green'
                      : ''
                  }"
                >
                  ${
                    supplier.active
                      ? 'Activo'
                      : 'Inactivo'
                  }
                </span>
              </td>
            </tr>
          `
        ).join('')
      : `
          <tr>
            <td
              colspan="5"
              class="purchases-empty-cell"
            >
              No hay proveedores registrados.
            </td>
          </tr>
        `;


  return `
    <div class="purchases-page">

      <div class="toolbar purchases-toolbar">

        <div>
          <p class="eyebrow">
            ABASTECIMIENTO
          </p>

          <h2>
            Compras y proveedores
          </h2>
        </div>

        <div class="purchases-actions">

          <button
            type="button"
            class="btn secondary"
            id="new-supplier"
          >
            + Nuevo proveedor
          </button>

          <button
            type="button"
            class="btn primary"
            id="new-purchase"
          >
            + Registrar compra
          </button>

        </div>

      </div>


      <section class="purchases-summary">

        <article class="card purchase-kpi">
          <small>
            PROVEEDORES ACTIVOS
          </small>

          <strong>
            ${activeSuppliers.length}
          </strong>
        </article>


        <article class="card purchase-kpi">
          <small>
            COMPRAS REGISTRADAS
          </small>

          <strong>
            ${purchases.length}
          </strong>
        </article>


        <article class="card purchase-kpi">
          <small>
            TOTAL COMPRADO
          </small>

          <strong>
            ${money(totalPurchased)}
          </strong>
        </article>


        <article class="card purchase-kpi">
          <small>
            ÚLTIMA COMPRA
          </small>

          <strong>
            ${
              lastPurchase
                ? money(lastPurchase.total)
                : money(0)
            }
          </strong>

          <span>
            ${
              lastPurchase
                ? purchaseEscape(
                    lastPurchase.supplier_name
                  )
                : 'Sin compras'
            }
          </span>
        </article>

      </section>


      <section class="card">

        <div class="card-head">

          <div>
            <p class="eyebrow">
              HISTORIAL
            </p>

            <h2>
              Compras recientes
            </h2>
          </div>

          <span class="pill">
            ${purchases.length}
          </span>

        </div>


        <div class="table-wrap">

          <table>

            <thead>
              <tr>
                <th>Compra</th>
                <th>Proveedor</th>
                <th>Total</th>
                <th>Estado</th>
                <th>Fecha</th>
                <th></th>
              </tr>
            </thead>

            <tbody>
              ${purchasesRows}
            </tbody>

          </table>

        </div>

      </section>


      <section class="card">

        <div class="card-head">

          <div>
            <p class="eyebrow">
              DIRECTORIO
            </p>

            <h2>
              Proveedores
            </h2>
          </div>

          <span class="pill">
            ${suppliers.length}
          </span>

        </div>


        <div class="table-wrap">

          <table>

            <thead>
              <tr>
                <th>Proveedor</th>
                <th>NIT / documento</th>
                <th>Contacto</th>
                <th>Teléfono</th>
                <th>Estado</th>
              </tr>
            </thead>

            <tbody>
              ${supplierRows}
            </tbody>

          </table>

        </div>

      </section>

    </div>
  `;
}


function openSupplierModal() {

  document
    .querySelector('#supplier-modal')
    ?.remove();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="supplier-modal"
      >

        <div class="modal">

          <div class="card-head">

            <div>
              <p class="eyebrow">
                PROVEEDORES
              </p>

              <h2>
                Nuevo proveedor
              </h2>
            </div>

            <button
              type="button"
              class="icon-btn purchases-modal-close"
            >
              ×
            </button>

          </div>


          <div class="form-grid">

            <label class="field full">
              Nombre

              <input
                id="supplier-name"
                type="text"
                maxlength="160"
              />
            </label>


            <label class="field">
              NIT / documento

              <input
                id="supplier-document"
                type="text"
              />
            </label>


            <label class="field">
              Teléfono

              <input
                id="supplier-phone"
                type="text"
              />
            </label>


            <label class="field">
              Contacto

              <input
                id="supplier-contact"
                type="text"
              />
            </label>


            <label class="field">
              Correo

              <input
                id="supplier-email"
                type="email"
              />
            </label>


            <label class="field full">
              Dirección

              <input
                id="supplier-address"
                type="text"
              />
            </label>


            <label class="field full">
              Observaciones

              <textarea
                id="supplier-notes"
                rows="3"
              ></textarea>
            </label>

          </div>


          <div class="modal-actions">

            <button
              type="button"
              class="btn secondary purchases-modal-close"
            >
              Cancelar
            </button>

            <button
              type="button"
              class="btn primary"
              id="save-supplier"
            >
              Guardar proveedor
            </button>

          </div>

        </div>

      </div>
    `
  );

  document
    .querySelector('#supplier-name')
    ?.focus();
}


async function saveSupplier() {

  const name =
    document
      .querySelector('#supplier-name')
      ?.value
      .trim();

  if (!name || name.length < 2) {
    toast(
      'Ingresa el nombre del proveedor.'
    );
    return;
  }

  const payload = {
    name,

    document:
      document
        .querySelector('#supplier-document')
        ?.value
        .trim() || null,

    phone:
      document
        .querySelector('#supplier-phone')
        ?.value
        .trim() || null,

    email:
      document
        .querySelector('#supplier-email')
        ?.value
        .trim() || null,

    address:
      document
        .querySelector('#supplier-address')
        ?.value
        .trim() || null,

    contact_name:
      document
        .querySelector('#supplier-contact')
        ?.value
        .trim() || null,

    notes:
      document
        .querySelector('#supplier-notes')
        ?.value
        .trim() || null
  };

  const button =
    document.querySelector(
      '#save-supplier'
    );

  if (button) {
    button.disabled = true;
    button.textContent =
      'Guardando...';
  }

  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/suppliers`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify(payload)
        }
      );

    if (!response.ok) {
      const error =
        await response
          .json()
          .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible crear el proveedor.'
      );
    }

    document
      .querySelector('#supplier-modal')
      ?.remove();

    await loadPurchasesModuleData();

    render('purchases');

    toast(
      'Proveedor creado correctamente.'
    );

  }
  catch (error) {

    toast(error.message);

    if (button) {
      button.disabled = false;
      button.textContent =
        'Guardar proveedor';
    }
  }
}


function openPurchaseModal() {

  const suppliers =
    (state.suppliers || [])
      .filter(
        supplier => supplier.active
      );

  if (!suppliers.length) {
    toast(
      'Primero debes crear un proveedor activo.'
    );
    return;
  }

  const products =
    (state.products || [])
      .filter(
        product =>
          product.id != null &&
          product.active !== false
      );

  if (!products.length) {
    toast(
      'No hay productos activos.'
    );
    return;
  }

  purchaseDraft = [];

  document
    .querySelector('#purchase-modal')
    ?.remove();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="purchase-modal"
      >

        <div class="modal purchase-modal">

          <div class="card-head">

            <div>
              <p class="eyebrow">
                ENTRADA DE INVENTARIO
              </p>

              <h2>
                Registrar compra
              </h2>
            </div>

            <button
              type="button"
              class="icon-btn purchases-modal-close"
            >
              ×
            </button>

          </div>


          <label class="field full">
            Proveedor

            <select id="purchase-supplier">

              ${
                suppliers.map(
                  supplier => `
                    <option value="${supplier.id}">
                      ${purchaseEscape(
                        supplier.name
                      )}
                    </option>
                  `
                ).join('')
              }

            </select>
          </label>


          <div class="purchase-add-product">

            <label class="field purchase-product-field">
              Producto

              <select id="purchase-product">

                ${
                  products.map(
                    product => `
                      <option value="${product.id}">
                        ${purchaseEscape(
                          product.name
                        )}
                        ${
                          product.sku
                            ? ` · ${purchaseEscape(
                                product.sku
                              )}`
                            : ''
                        }
                      </option>
                    `
                  ).join('')
                }

              </select>
            </label>


            <label class="field">
              Cantidad

              <input
                id="purchase-quantity"
                type="number"
                min="0.01"
                step="0.01"
                value="1"
              />
            </label>


            <label class="field">
              Costo unitario

              <input
                id="purchase-unit-cost"
                type="number"
                min="0"
                step="100"
                value="0"
              />
            </label>


            <button
              type="button"
              class="btn secondary"
              id="purchase-add-item"
            >
              + Agregar
            </button>

          </div>


          <div
            class="purchase-draft"
            id="purchase-draft"
          ></div>


          <label
            class="field full"
            style="margin-top:16px"
          >
            Observaciones

            <textarea
              id="purchase-notes"
              rows="3"
            ></textarea>
          </label>


          <div class="modal-actions">

            <div class="purchase-grand-total">

              <small>TOTAL</small>

              <strong id="purchase-total">
                ${money(0)}
              </strong>

            </div>


            <button
              type="button"
              class="btn secondary purchases-modal-close"
            >
              Cancelar
            </button>


            <button
              type="button"
              class="btn primary"
              id="save-purchase"
            >
              Registrar compra
            </button>

          </div>

        </div>

      </div>
    `
  );

  syncPurchaseProductCost();
  renderPurchaseDraft();
}


function syncPurchaseProductCost() {

  const productId =
    Number(
      document
        .querySelector('#purchase-product')
        ?.value
    );

  const product =
    state.products.find(
      item =>
        Number(item.id) === productId
    );

  const input =
    document.querySelector(
      '#purchase-unit-cost'
    );

  if (input && product) {
    input.value =
      Number(
        product.cost_price || 0
      );
  }
}


function addPurchaseDraftItem() {

  const productId =
    Number(
      document
        .querySelector('#purchase-product')
        ?.value
    );

  const quantity =
    Number(
      document
        .querySelector('#purchase-quantity')
        ?.value
    );

  const unitCost =
    Number(
      document
        .querySelector('#purchase-unit-cost')
        ?.value
    );

  if (!productId) {
    toast('Selecciona un producto.');
    return;
  }

  if (
    !Number.isFinite(quantity) ||
    quantity <= 0
  ) {
    toast(
      'Ingresa una cantidad válida.'
    );
    return;
  }

  if (
    !Number.isFinite(unitCost) ||
    unitCost < 0
  ) {
    toast(
      'Ingresa un costo válido.'
    );
    return;
  }

  const product =
    state.products.find(
      item =>
        Number(item.id) === productId
    );

  if (!product) {
    toast(
      'Producto no encontrado.'
    );
    return;
  }

  const existing =
    purchaseDraft.find(
      item =>
        item.product_id === productId
    );

  if (existing) {
    existing.quantity += quantity;
    existing.unit_cost = unitCost;
  }
  else {
    purchaseDraft.push({
      product_id:
        productId,

      name:
        product.name,

      sku:
        product.sku,

      quantity,

      unit_cost:
        unitCost
    });
  }

  renderPurchaseDraft();
}


function renderPurchaseDraft() {

  const container =
    document.querySelector(
      '#purchase-draft'
    );

  if (!container) {
    return;
  }

  if (!purchaseDraft.length) {

    container.innerHTML = `
      <div class="purchase-draft-empty">
        Agrega los productos recibidos
        en esta compra.
      </div>
    `;

  }
  else {

    container.innerHTML = `
      <div class="table-wrap">

        <table>

          <thead>
            <tr>
              <th>Producto</th>
              <th>Cantidad</th>
              <th>Costo</th>
              <th>Subtotal</th>
              <th></th>
            </tr>
          </thead>

          <tbody>

            ${
              purchaseDraft.map(
                item => `
                  <tr>

                    <td>
                      <strong>
                        ${purchaseEscape(
                          item.name
                        )}
                      </strong>

                      <small>
                        ${purchaseEscape(
                          item.sku || ''
                        )}
                      </small>
                    </td>

                    <td>
                      ${item.quantity}
                    </td>

                    <td>
                      ${money(
                        item.unit_cost
                      )}
                    </td>

                    <td>
                      <strong>
                        ${money(
                          item.quantity *
                          item.unit_cost
                        )}
                      </strong>
                    </td>

                    <td>
                      <button
                        type="button"
                        class="btn secondary purchase-remove-item"
                        data-product-id="${item.product_id}"
                      >
                        Quitar
                      </button>
                    </td>

                  </tr>
                `
              ).join('')
            }

          </tbody>

        </table>

      </div>
    `;
  }

  const total =
    purchaseDraft.reduce(
      (sum, item) =>
        sum +
        (
          Number(item.quantity) *
          Number(item.unit_cost)
        ),
      0
    );

  const totalElement =
    document.querySelector(
      '#purchase-total'
    );

  if (totalElement) {
    totalElement.textContent =
      money(total);
  }
}


async function savePurchase() {

  const supplierId =
    Number(
      document
        .querySelector('#purchase-supplier')
        ?.value
    );

  if (!supplierId) {
    toast(
      'Selecciona un proveedor.'
    );
    return;
  }

  if (!purchaseDraft.length) {
    toast(
      'Agrega al menos un producto.'
    );
    return;
  }

  const payload = {
    supplier_id:
      supplierId,

    notes:
      document
        .querySelector('#purchase-notes')
        ?.value
        .trim() || null,

    items:
      purchaseDraft.map(
        item => ({
          product_id:
            item.product_id,

          quantity:
            item.quantity,

          unit_cost:
            item.unit_cost
        })
      )
  };

  const button =
    document.querySelector(
      '#save-purchase'
    );

  if (button) {
    button.disabled = true;
    button.textContent =
      'Registrando...';
  }

  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/purchases`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify(payload)
        }
      );

    if (!response.ok) {

      const error =
        await response
          .json()
          .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible registrar la compra.'
      );
    }

    const result =
      await response.json();

    document
      .querySelector('#purchase-modal')
      ?.remove();

    purchaseDraft = [];

    await syncFromApi(false);

    toast(
      `${result.number} registrada por ${money(
        result.total
      )}`
    );

  }
  catch (error) {

    toast(error.message);

    if (button) {
      button.disabled = false;
      button.textContent =
        'Registrar compra';
    }
  }
}


async function openPurchaseDetail(
  purchaseId
) {

  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/purchases/${purchaseId}`
      );

    if (!response.ok) {

      const error =
        await response
          .json()
          .catch(() => ({}));

      throw new Error(
        error.detail ||
        'No fue posible cargar la compra.'
      );
    }

    const purchase =
      await response.json();

    const rows =
      (purchase.items || [])
        .map(
          item => `
            <tr>
              <td>
                ${purchaseEscape(
                  item.product_name
                )}
              </td>

              <td>
                ${item.quantity}
              </td>

              <td>
                ${money(
                  item.unit_cost
                )}
              </td>

              <td>
                ${money(
                  item.subtotal
                )}
              </td>
            </tr>
          `
        )
        .join('');

    document
      .querySelector(
        '#purchase-detail-modal'
      )
      ?.remove();

    document.body.insertAdjacentHTML(
      'beforeend',
      `
        <div
          class="modal-overlay"
          id="purchase-detail-modal"
        >

          <div class="modal">

            <div class="card-head">

              <div>
                <p class="eyebrow">
                  COMPRA
                </p>

                <h2>
                  ${purchaseEscape(
                    purchase.number
                  )}
                </h2>
              </div>

              <button
                type="button"
                class="icon-btn purchases-modal-close"
              >
                ×
              </button>

            </div>


            <div class="purchase-detail-meta">

              <div>
                <small>Proveedor</small>

                <strong>
                  ${purchaseEscape(
                    purchase.supplier_name
                  )}
                </strong>
              </div>

              <div>
                <small>Fecha</small>

                <strong>
                  ${purchaseDate(
                    purchase.created_at
                  )}
                </strong>
              </div>

              <div>
                <small>Total</small>

                <strong>
                  ${money(
                    purchase.total
                  )}
                </strong>
              </div>

            </div>


            <div class="table-wrap">

              <table>

                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Cantidad</th>
                    <th>Costo</th>
                    <th>Subtotal</th>
                  </tr>
                </thead>

                <tbody>
                  ${rows}
                </tbody>

              </table>

            </div>

          </div>

        </div>
      `
    );

  }
  catch (error) {
    toast(error.message);
  }
}


/* PURCHASE EVENTS */

document.addEventListener(
  'click',
  event => {

    if (
      event.target.closest(
        '#new-supplier'
      )
    ) {
      openSupplierModal();
      return;
    }

    if (
      event.target.closest(
        '#save-supplier'
      )
    ) {
      saveSupplier();
      return;
    }

    if (
      event.target.closest(
        '#new-purchase'
      )
    ) {
      openPurchaseModal();
      return;
    }

    if (
      event.target.closest(
        '#purchase-add-item'
      )
    ) {
      addPurchaseDraftItem();
      return;
    }

    const removeButton =
      event.target.closest(
        '.purchase-remove-item'
      );

    if (removeButton) {

      const productId =
        Number(
          removeButton.dataset.productId
        );

      purchaseDraft =
        purchaseDraft.filter(
          item =>
            item.product_id !== productId
        );

      renderPurchaseDraft();
      return;
    }

    if (
      event.target.closest(
        '#save-purchase'
      )
    ) {
      savePurchase();
      return;
    }

    const detailButton =
      event.target.closest(
        '.purchase-detail-btn'
      );

    if (detailButton) {

      openPurchaseDetail(
        Number(
          detailButton.dataset.purchaseId
        )
      );

      return;
    }

    const closeButton =
      event.target.closest(
        '.purchases-modal-close'
      );

    if (closeButton) {

      closeButton
        .closest('.modal-overlay')
        ?.remove();

    }

  }
);


document.addEventListener(
  'change',
  event => {

    if (
      event.target.matches(
        '#purchase-product'
      )
    ) {
      syncPurchaseProductCost();
    }

  }
);



const views = {
  dashboard: {
    title: 'Resumen de hoy',
    render: dashboard
  },
  sales: {
    title: 'Ventas y caja',
    render: sales
  },
  inventory: {
    title: 'Inventario',
    render: inventory
  },
  expenses: {
    title: 'Gastos',
    render: expenses
  }}

views.audit = {
  title: 'Auditoría',
  render: auditView
};

views.purchases = {
  title: 'Compras y proveedores',
  render: purchasesView
};

views.invoices = {
  title: 'Facturación electrónica',
  render: invoicesView
};

;

let currentView =
  sessionStorage.getItem('lp-current-view') ||
  'dashboard';


let dashboardPeriod =
  sessionStorage.getItem(
    'gato-dashboard-period'
  ) || 'day';





function filterInventoryProducts() {
  const searchInput =
    document.querySelector(
      '#inventory-search'
    );

  const stockFilter =
    document.querySelector(
      '#inventory-stock-filter'
    );

  const qrFilter =
    document.querySelector(
      '#inventory-qr-filter'
    );

  const sortSelect =
    document.querySelector(
      '#inventory-sort'
    );

  const query =
    searchInput?.value
      .trim()
      .toLowerCase()
    || '';

  const stockValue =
    stockFilter?.value
    || 'all';

  const qrValue =
    qrFilter?.value
    || 'all';

  const sortValue =
    sortSelect?.value
    || 'name-asc';

  const tbody =
    document.querySelector(
      '.inventory-product-row'
    )?.parentElement;

  const rows = [
    ...document.querySelectorAll(
      '.inventory-product-row'
    )
  ];

  let visible = 0;

  rows.forEach(row => {
    const searchable =
      row.dataset.productSearch || '';

    const stockStatus =
      row.dataset.stockStatus || '';

    const qrStatus =
      row.dataset.qrStatus || '';

    const matchesSearch =
      !query ||
      searchable.includes(query);

    const matchesStock =
      stockValue === 'all' ||
      stockStatus === stockValue;

    const matchesQr =
      qrValue === 'all' ||
      qrStatus === qrValue;

    const matches =
      matchesSearch &&
      matchesStock &&
      matchesQr;

    row.style.display =
      matches
        ? ''
        : 'none';

    if (matches) {
      visible += 1;
    }
  });

  rows.sort((a, b) => {
    const nameA =
      a.dataset.productName || '';

    const nameB =
      b.dataset.productName || '';

    const stockA =
      Number(
        a.dataset.productStock || 0
      );

    const stockB =
      Number(
        b.dataset.productStock || 0
      );

    const priceA =
      Number(
        a.dataset.productPrice || 0
      );

    const priceB =
      Number(
        b.dataset.productPrice || 0
      );

    switch (sortValue) {

      case 'name-desc':
        return nameB.localeCompare(
          nameA,
          'es'
        );

      case 'stock-asc':
        return stockA - stockB;

      case 'stock-desc':
        return stockB - stockA;

      case 'price-asc':
        return priceA - priceB;

      case 'price-desc':
        return priceB - priceA;

      case 'name-asc':
      default:
        return nameA.localeCompare(
          nameB,
          'es'
        );
    }
  });

  if (tbody) {
    rows.forEach(row => {
      tbody.appendChild(row);
    });

    const empty =
      document.querySelector(
        '#inventory-search-empty'
      );

    if (empty) {
      tbody.appendChild(empty);
    }
  }

  const empty =
    document.querySelector(
      '#inventory-search-empty'
    );

  if (empty) {
    empty.style.display =
      visible === 0
        ? ''
        : 'none';
  }
}



/* ============================================================
   TABLE PAGINATION
============================================================ */

const tablePaginationState = {};


function paginationKey(
  table,
  index
) {
  return (
    table.dataset.paginationKey
    || `${currentView}-table-${index}`
  );
}


function getPaginationState(key) {
  if (!tablePaginationState[key]) {
    tablePaginationState[key] = {
      page: 1,
      pageSize: 10
    };
  }

  return tablePaginationState[key];
}


function tableRowsAvailable(tbody) {
  const rows = [
    ...tbody.querySelectorAll(
      ':scope > tr'
    )
  ];

  rows.forEach(
    row => {
      row.classList.remove(
        'pagination-hidden'
      );
    }
  );

  return rows.filter(
    row => {
      if (row.hidden) {
        return false;
      }

      if (
        row.style.display === 'none'
      ) {
        return false;
      }

      return true;
    }
  );
}


function updateTablePagination(
  table,
  index = 0
) {
  const tbody =
    table.querySelector('tbody');

  if (!tbody) {
    return;
  }

  const key =
    paginationKey(
      table,
      index
    );

  table.dataset.paginationKey =
    key;

  const state =
    getPaginationState(key);

  const rows =
    tableRowsAvailable(tbody);

  const total =
    rows.length;

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        total / state.pageSize
      )
    );

  if (state.page > totalPages) {
    state.page =
      totalPages;
  }

  if (state.page < 1) {
    state.page = 1;
  }

  const start =
    (state.page - 1)
    * state.pageSize;

  const end =
    start
    + state.pageSize;

  rows.forEach(
    (row, rowIndex) => {
      row.classList.toggle(
        'pagination-hidden',
        !(
          rowIndex >= start
          && rowIndex < end
        )
      );
    }
  );

  const wrapper =
    table.closest(
      '.table-wrap'
    )
    || table.parentElement;

  if (!wrapper) {
    return;
  }

  let pagination =
    wrapper.querySelector(
      ':scope > .table-pagination'
    );

  if (!pagination) {
    pagination =
      document.createElement(
        'div'
      );

    pagination.className =
      'table-pagination';

    wrapper.appendChild(
      pagination
    );
  }

  const from =
    total
      ? start + 1
      : 0;

  const to =
    Math.min(
      end,
      total
    );

  pagination.innerHTML = `
    <div
      class="table-pagination-info"
    >
      Mostrando
      <strong>${from}-${to}</strong>
      de
      <strong>${total}</strong>
    </div>

    <div
      class="table-pagination-actions"
    >

      <label
        class="table-page-size"
      >
        <span>
          Filas
        </span>

        <select
          class="input pagination-size"
        >
          ${[10, 25, 50]
      .map(
        size => `
                <option
                  value="${size}"
                  ${Number(state.pageSize)
            === size
            ? 'selected'
            : ''
          }
                >
                  ${size}
                </option>
              `
      )
      .join('')
    }
        </select>
      </label>


      <button
        type="button"
        class="
          btn
          secondary
          pagination-prev
        "
        ${state.page <= 1
      ? 'disabled'
      : ''
    }
      >
        ←
      </button>


      <span
        class="table-page-indicator"
      >
        ${state.page}
        /
        ${totalPages}
      </span>


      <button
        type="button"
        class="
          btn
          secondary
          pagination-next
        "
        ${state.page >= totalPages
      ? 'disabled'
      : ''
    }
      >
        →
      </button>

    </div>
  `;


  pagination
    .querySelector(
      '.pagination-prev'
    )
    ?.addEventListener(
      'click',
      () => {
        state.page -= 1;

        updateTablePagination(
          table,
          index
        );
      }
    );


  pagination
    .querySelector(
      '.pagination-next'
    )
    ?.addEventListener(
      'click',
      () => {
        state.page += 1;

        updateTablePagination(
          table,
          index
        );
      }
    );


  pagination
    .querySelector(
      '.pagination-size'
    )
    ?.addEventListener(
      'change',
      event => {
        state.pageSize =
          Number(
            event.target.value
          )
          || 10;

        state.page = 1;

        updateTablePagination(
          table,
          index
        );
      }
    );
}


function setupCurrentViewPagination() {

  // Dashboard y Auditoría quedan sin paginación genérica.
  if (
    currentView === 'dashboard'
  ) {
    return;
  }


  const tables = [
    ...document.querySelectorAll(
      '#app table'
    )
  ];


  tables.forEach(
    (table, index) => {

      // ======================================================
      // CLAVES ESTABLES PARA INVENTARIO
      // ======================================================

      if (
        currentView === 'inventory'
        && table.id === 'inventory-movements-table'
      ) {
        table.dataset.paginationKey =
          'inventory-movements';
      }

      else if (
        currentView === 'inventory'
        && table.querySelector(
          '.inventory-product-row'
        )
      ) {
        table.dataset.paginationKey =
          'inventory-products';
      }

      else if (
        !table.dataset.paginationKey
      ) {
        table.dataset.paginationKey =
          `${currentView}-table-${index}`;
      }


      // ======================================================
      // PAGINAR TODAS LAS TABLAS DE LA VISTA
      // ======================================================

      updateTablePagination(
        table,
        index
      );
    }
  );
}


function refreshCurrentViewPagination() {
  requestAnimationFrame(
    () => {
      setupCurrentViewPagination();
    }
  );

  setTimeout(
    () => {
      setupCurrentViewPagination();
    },
    0
  );
}



document.addEventListener(
  'input',
  event => {
    if (
      event.target.matches(
        'input[type="search"], input[data-filter]'
      )
    ) {
      setTimeout(
        refreshCurrentViewPagination,
        0
      );
    }
  }
);


document.addEventListener(
  'change',
  event => {
    if (
      event.target.closest(
        '.table-pagination'
      )
    ) {
      return;
    }

    if (
      event.target.matches(
        'select, input'
      )
    ) {
      setTimeout(
        refreshCurrentViewPagination,
        0
      );
    }
  }
);



function updateActiveNavigation() {

  document
    .querySelectorAll(
      '#nav .nav-item[data-view]'
    )
    .forEach(
      button => {

        const isActive =
          button.dataset.view === currentView;

        button.classList.toggle(
          'active',
          isActive
        );

        if (isActive) {
          button.setAttribute(
            'aria-current',
            'page'
          );
        } else {
          button.removeAttribute(
            'aria-current'
          );
        }
      }
    );

  // Sync drawer nav
  document
    .querySelectorAll(
      '#drawer-nav .drawer-item[data-view], #drawer-nav-admin .drawer-item[data-view]'
    )
    .forEach(
      button => {
        button.classList.toggle(
          'active',
          button.dataset.view === currentView
        );
      }
    );

  // Sync bottom nav
  document
    .querySelectorAll(
      '#bottom-nav .bottom-nav-item[data-view]'
    )
    .forEach(
      button => {
        button.classList.toggle(
          'active',
          button.dataset.view === currentView
        );
      }
    );

  document
    .querySelectorAll(
      '#nav .nav-item[data-view="invoices"]'
    )
    .forEach(
      button => {
        if (state.currentUser?.role === 'ADMIN') {
          button.removeAttribute('hidden');
        }
      }
    );
}


/* ============================================================
   INVOICE DETAIL EVENTS
============================================================ */

document.addEventListener(
  'click',
  event => {
    const invoiceDetailBtn =
      event.target.closest('.invoice-detail-btn');

    if (invoiceDetailBtn) {
      event.preventDefault();
      event.stopPropagation();

      openInvoiceDetail(
        Number(invoiceDetailBtn.dataset.invoiceId)
      );
    }
  }
);



/* ============================================================
   OPEN ACCOUNTS EVENTS
============================================================ */

document.addEventListener(
  'click',
  event => {

    const newAccount =
      event.target.closest(
        '#new-open-account'
      );

    if (newAccount) {

      event.preventDefault();

      openAccountModal();

      return;
    }


    const addItem =
      event.target.closest(
        '.open-account-add-item'
      );

    if (addItem) {

      event.preventDefault();

      openAccountConsumptionModal(
        Number(
          addItem.dataset.accountId
        )
      );

      return;
    }


    const closeAccount =
      event.target.closest(
        '.open-account-close'
      );

    if (closeAccount) {

      event.preventDefault();

      openCloseAccountModal(
        Number(
          closeAccount.dataset.accountId
        )
      );

      return;
    }

  }
);


function render(view = currentView || 'dashboard') {
  if (
    view === 'audit'
    && !systemAuditLoaded
  ) {
    openAuditModule();
    return;
  }

  if (
    view === 'invoices'
    && state.currentUser?.role !== 'ADMIN'
  ) {
    view = 'dashboard';
  }

  if (
    view === 'invoices'
    && !electronicInvoicesLoaded
  ) {
    currentView = 'invoices';
    loadElectronicInvoices().then(() => render('invoices'));
    return;
  }



  if (
    !view ||
    !views[view] ||
    typeof views[view].render !== 'function'
  ) {
    console.warn(
      `Vista inválida: ${view}. Volviendo a dashboard.`
    );

    view = 'dashboard';
  }

  currentView = view;

  updateActiveNavigation();

  sessionStorage.setItem(
    'lp-current-view',
    currentView
  );

  const viewConfig =
    views[view];

  document.querySelector('#view-title').textContent =
    viewConfig.title;

  app.innerHTML =
    viewConfig.render();

  updateActiveNavigation();

  // Aplicar paginación cuando la tabla ya existe en el DOM.
  refreshCurrentViewPagination();

  document.querySelectorAll('[data-view]').forEach(element => {
    element.onclick = () => {
      const targetView =
        element.dataset.view;

      if (targetView === 'purchases') {
        openPurchasesModule();
        return;
      }

      if (targetView === 'users') {
        openUsersModule();
        return;
      }

      if (targetView === 'audit') {
        openAuditModule();
        return;
      }

      render(targetView);
    };
  });


  document
    .querySelector(
      '#dashboard-period'
    )
    ?.addEventListener(
      'change',
      event => {

        dashboardPeriod =
          event.target.value;

        sessionStorage.setItem(
          'gato-dashboard-period',
          dashboardPeriod
        );

        render('dashboard');
      }
    );


  applyRoleActionPermissions();

  bindUsersModuleEvents();

  document
    .querySelector('#new-sale')
    ?.addEventListener(
      'click',
      openSaleModal
    );

  document
    .querySelector('#admin-generate-qr')
    ?.addEventListener(
      'click',
      generateSelectedProductQr
    );

  document
    .querySelector('#admin-scan-qr')
    ?.addEventListener(
      'click',
      openQrScanner
    );

  document
    .querySelector('#open-company-info-btn')
    ?.addEventListener(
      'click',
      openCompanyInfoModal
    );

  document
    .querySelector('#admin-delete-product')
    ?.addEventListener(
      'click',
      deleteSelectedProduct
    );

  document
    .querySelector('#admin-clear-session')
    ?.addEventListener(
      'click',
      () => {
        sessionStorage.removeItem(
          'lp-admin-key'
        );

        toast(
          'Sesión administrativa cerrada.'
        );
      }
    );


  document
    .querySelectorAll(
      '.product-qr-btn'
    )
    .forEach(button => {
      button.addEventListener(
        'click',
        event => {
          event.preventDefault();
          event.stopPropagation();

          currentView = 'inventory';

          generateProductQr(
            button.dataset.productId
          );
        }
      );
    });

  document
    .querySelectorAll(
      '.product-edit-btn'
    )
    .forEach(
      button => {

        button.addEventListener(
          'click',
          event => {

            event.preventDefault();
            event.stopPropagation();

            openEditProductModal(
              Number(
                button.dataset.productId
              )
            );
          }
        );
      }
    );


  document
    .querySelectorAll(
      '.product-delete-qr-btn'
    )
    .forEach(button => {
      button.addEventListener(
        'click',
        event => {
          event.preventDefault();
          event.stopPropagation();

          currentView = 'inventory';

          deleteProductQr(
            button.dataset.productId
          );
        }
      );
    });

  document
    .querySelectorAll(
      '.product-delete-btn'
    )
    .forEach(button => {
      button.addEventListener(
        'click',
        event => {
          event.preventDefault();
          event.stopPropagation();

          currentView = 'inventory';

          deleteProductById(
            button.dataset.productId
          );
        }
      );
    });



  document
    .querySelector(
      '#repeat-last-sale'
    )
    ?.addEventListener(
      'click',
      repeatLastSale
    );


  document
    .querySelector('#inventory-search')
    ?.addEventListener(
      'input',
      filterInventoryProducts
    );


  document
    .querySelector(
      '#inventory-stock-filter'
    )
    ?.addEventListener(
      'change',
      filterInventoryProducts
    );

  document
    .querySelector(
      '#inventory-qr-filter'
    )
    ?.addEventListener(
      'change',
      filterInventoryProducts
    );


  document
    .querySelector(
      '#inventory-sort'
    )
    ?.addEventListener(
      'change',
      filterInventoryProducts
    );


  if (
    document.querySelector(
      '#inventory-search'
    )
  ) {
    filterInventoryProducts();
  }

  document
    .querySelector('#new-product')
    ?.addEventListener(
      'click',
      openProductModal
    );

  document
    .querySelector('#new-adjustment')
    ?.addEventListener(
      'click',
      openInventoryAdjustmentModal
    );

  document
    .querySelector('#new-expense')
    ?.addEventListener(
      'click',
      openExpenseModal
    );

}


/* ============================================================
   API SYNC
============================================================ */

async function syncFromApi(showToast = true) {
  try {
    const [
      products,
      sales,
      expenses,
      inventoryMovements,
      cashRegister,
      openAccounts,
      inventoryHistory
    ] = await Promise.all([
      fetch(
        `${API_BASE}/api/products`
      ).then(response =>
        response.ok
          ? response.json()
          : Promise.reject()
      ),

      authenticatedFetch(`${API_BASE}/api/sales`
      ).then(response =>
        response.ok
          ? response.json()
          : Promise.reject()
      ),

      authenticatedFetch(`${API_BASE}/api/expenses`
      ).then(response =>
        response.ok
          ? response.json()
          : Promise.reject()
      ),

      fetch(
        `${API_BASE}/api/inventory/movements`
      ).then(response =>
        response.ok
          ? response.json()
          : Promise.reject()
      ),

      fetch(
        `${API_BASE}/api/cash-register/current`
      ).then(response =>
        response.ok
          ? response.json()
          : Promise.reject()
      ),

      authenticatedFetch(
        `${API_BASE}/api/open-accounts`
      ).then(
        response =>
          response.ok
            ? response.json()
            : []
      ),

      fetch(
        `${API_BASE}/api/inventory/history?limit=2000`
      ).then(response =>
        response.ok
          ? response.json()
          : []
      )
    ]);

    state.products = products;
    state.inventoryMovements = inventoryMovements;
    state.inventoryHistory = inventoryHistory;

    state.sales = sales.map(sale => ({
      db_id: sale.id,
      id: sale.number,
      customer_name: sale.customer_name,
      detail:
        `${sale.customer_name} · venta registrada`,
      total: Number(sale.total),
      payment: sale.payment_method,
      status: sale.status,
      created_at: sale.created_at
    }));

    state.expenses = expenses.map(expense => ({
      concept: expense.concept,
      provider:
        expense.provider ||
        'Sin proveedor',
      value: Number(expense.value),
      date:
        new Date(
          expense.created_at
        ).toLocaleDateString('es-CO'),
      created_at: expense.created_at
    }));

    state.cashRegister =
      cashRegister || {
        status: 'CLOSED',
        session: null
      };

    state.openAccounts =
      Array.isArray(openAccounts)
        ? openAccounts
        : [];

    renderStockNotifications();

    if (currentView === 'audit') {
      await loadSystemAudit();

      render('audit');

      bindAuditEvents();
      renderAuditTimeline();

    }
    else if (currentView === 'purchases') {

      if (
        state.currentUser?.role === 'ADMIN'
      ) {
        await loadPurchasesModuleData();

        render('purchases');
      }
      else {
        currentView = 'dashboard';

        sessionStorage.setItem(
          'lp-current-view',
          'dashboard'
        );

        render('dashboard');
      }

    }
    else {
      render(currentView);
    }

    if (showToast) {
      toast(
        'Datos sincronizados con la API'
      );
    }

    return true;

  } catch (error) {
    console.info(
      'API no disponible; usando datos de demostración'
    );

    return false;
  }
}



/* ============================================================
   KEYBOARD SHORTCUTS
============================================================ */

function keyboardAllowedRole() {
  return (
    state.currentUser?.role === 'ADMIN'
    || state.currentUser?.role === 'VENDEDOR'
  );
}


function keyboardSaleModalOpen() {
  return Boolean(
    document.querySelector('#sale-modal')
  );
}


function keyboardClickByText(
  scope,
  text
) {

  const root =
    typeof scope === 'string'
      ? document.querySelector(scope)
      : scope;

  if (!root) {
    return false;
  }

  const normalized =
    text
      .trim()
      .toLowerCase();

  const button =
    [...root.querySelectorAll('button')]
      .find(item =>
        item.textContent
          ?.trim()
          .toLowerCase()
          .includes(normalized)
      );

  if (!button || button.disabled) {
    return false;
  }

  button.click();

  return true;
}


function keyboardFocusSearch() {

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  if (!search) {
    toast(
      'Abre una venta primero.'
    );
    return;
  }

  search.focus();
  search.select?.();
}


function keyboardFocusQuantity() {

  const input =
    document.querySelector(
      '#sale-quantity'
    );

  if (!input) {
    toast(
      'Abre una venta primero.'
    );
    return;
  }

  input.focus();
  input.select();
}


function keyboardSetQuantity(
  quantity
) {

  const input =
    document.querySelector(
      '#sale-quantity'
    );

  if (!input) {
    return false;
  }

  const value =
    Math.max(
      1,
      Number(quantity) || 1
    );

  input.value =
    String(value);

  input.dispatchEvent(
    new Event(
      'input',
      {
        bubbles: true
      }
    )
  );

  input.dispatchEvent(
    new Event(
      'change',
      {
        bubbles: true
      }
    )
  );

  return true;
}


function keyboardChangeQuantity(
  difference
) {

  const input =
    document.querySelector(
      '#sale-quantity'
    );

  if (!input) {
    return false;
  }

  const current =
    Number(input.value) || 1;

  return keyboardSetQuantity(
    current + difference
  );
}


function keyboardAddProduct() {

  if (!keyboardSaleModalOpen()) {
    toast(
      'Abre una venta primero.'
    );
    return;
  }

  /*
    No dependemos del ID del botón.
    Usamos el botón existente de la interfaz.
  */
  const clicked =
    keyboardClickByText(
      '#sale-modal',
      'Agregar producto'
    );

  if (!clicked) {
    toast(
      'Selecciona un producto antes de agregar.'
    );
  }
}


function keyboardConfirmSale() {

  const button =
    document.querySelector(
      '#confirm-sale'
    );

  if (!button) {
    toast(
      'No hay una venta abierta.'
    );
    return;
  }

  if (button.disabled) {
    return;
  }

  button.click();
}


function keyboardNewSale() {

  if (keyboardSaleModalOpen()) {
    keyboardFocusSearch();
    return;
  }

  const button =
    document.querySelector(
      '#new-sale'
    );

  if (button && !button.disabled) {
    button.click();
    return;
  }

  /*
    Si estamos en otra vista,
    primero vamos a Ventas.
  */
  const salesNav =
    document.querySelector(
      '#nav [data-view="sales"]'
    );

  if (salesNav) {
    salesNav.click();

    setTimeout(
      () => {
        document
          .querySelector('#new-sale')
          ?.click();
      },
      100
    );
  }
}


function keyboardGoSales() {

  const button =
    document.querySelector(
      '#nav [data-view="sales"]'
    );

  button?.click();
}


function keyboardCashAction() {

  /*
    Si hay modal de caja abierto,
    no hacemos nada para evitar
    confirmaciones accidentales.
  */
  const openCashModal =
    document.querySelector(
      '[id*="cash"][class*="modal"],' +
      '.modal-overlay [id*="cash"]'
    );

  if (openCashModal) {
    toast(
      'Completa o cierra la operación de caja actual.'
    );
    return;
  }

  const panel =
    document.querySelector(
      '#cash-register-panel'
    );

  if (!panel) {

    keyboardGoSales();

    setTimeout(
      keyboardCashAction,
      120
    );

    return;
  }

  const opened =
    keyboardClickByText(
      panel,
      'Abrir caja'
    );

  if (opened) {
    return;
  }

  const closed =
    keyboardClickByText(
      panel,
      'Cerrar caja'
    );

  if (!closed) {
    toast(
      'No hay una acción de caja disponible.'
    );
  }
}


function keyboardClearSearch() {

  const search =
    document.querySelector(
      '#sale-product-search'
    );

  if (!search) {
    return;
  }

  search.value = '';

  search.dispatchEvent(
    new Event(
      'input',
      {
        bubbles: true
      }
    )
  );

  search.focus();
}


function closeKeyboardShortcutHelp() {

  document
    .querySelector(
      '#keyboard-shortcuts-modal'
    )
    ?.remove();
}


function openKeyboardShortcutHelp() {

  closeKeyboardShortcutHelp();

  document.body.insertAdjacentHTML(
    'beforeend',
    `
      <div
        class="modal-overlay"
        id="keyboard-shortcuts-modal"
      >

        <div
          class="modal keyboard-shortcuts-modal"
        >

          <div class="card-head">

            <div>
              <p class="eyebrow">
                CAJA RÁPIDA
              </p>

              <h2>
                Atajos de teclado
              </h2>
            </div>

            <button
              type="button"
              class="icon-btn"
              id="close-keyboard-shortcuts"
              aria-label="Cerrar"
            >
              ×
            </button>

          </div>


          <div class="keyboard-shortcuts-grid">

            <div>
              <kbd>F2</kbd>
              <span>Nueva venta</span>
            </div>

            <div>
              <kbd>F3</kbd>
              <span>Buscar producto</span>
            </div>

            <div>
              <kbd>F4</kbd>
              <span>Agregar producto</span>
            </div>

            <div>
              <kbd>F6</kbd>
              <span>Cantidad</span>
            </div>

            <div>
              <kbd>F7</kbd>
              <span>Cantidad +1</span>
            </div>

            <div>
              <kbd>F8</kbd>
              <span>Cantidad -1</span>
            </div>

            <div>
              <kbd>F9</kbd>
              <span>Ventas y caja</span>
            </div>

            <div>
              <kbd>F10</kbd>
              <span>Abrir / cerrar caja</span>
            </div>

            <div>
              <kbd>Alt + 1</kbd>
              <span>Cantidad 1</span>
            </div>

            <div>
              <kbd>Alt + 2</kbd>
              <span>Cantidad 2</span>
            </div>

            <div>
              <kbd>Alt + 4</kbd>
              <span>Cantidad 4</span>
            </div>

            <div>
              <kbd>Alt + 6</kbd>
              <span>Cantidad 6</span>
            </div>

            <div>
              <kbd>Alt + 0</kbd>
              <span>Limpiar búsqueda</span>
            </div>

            <div class="important">
              <kbd>Ctrl + Enter</kbd>
              <span>Confirmar venta</span>
            </div>

            <div>
              <kbd>Esc</kbd>
              <span>Cerrar ventana</span>
            </div>

          </div>


          <p class="keyboard-shortcuts-note">
            Los atajos de venta funcionan para
            Administrador y Vendedor.
          </p>

        </div>

      </div>
    `
  );

  document
    .querySelector(
      '#close-keyboard-shortcuts'
    )
    ?.addEventListener(
      'click',
      closeKeyboardShortcutHelp
    );
}


function keyboardCloseTopModal() {

  if (
    document.querySelector(
      '#keyboard-shortcuts-modal'
    )
  ) {
    closeKeyboardShortcutHelp();
    return;
  }

  const overlays =
    [
      ...document.querySelectorAll(
        '.modal-overlay'
      )
    ];

  const overlay =
    overlays.at(-1);

  if (!overlay) {
    return;
  }

  const closeButton =
    overlay.querySelector(
      '.icon-btn,' +
      '[id^="close-"],' +
      '[id^="cancel-"],' +
      '.purchases-modal-close'
    );

  if (closeButton) {
    closeButton.click();
  }
}


document.addEventListener(
  'keydown',
  event => {

    if (!keyboardAllowedRole()) {
      return;
    }

    const key =
      event.key;

    /*
      F1 - ayuda
    */
    if (key === 'F1') {
      event.preventDefault();
      openKeyboardShortcutHelp();
      return;
    }


    /*
      ESC
    */
    if (key === 'Escape') {
      keyboardCloseTopModal();
      return;
    }


    /*
      CTRL + ENTER
      Confirmación deliberada.
    */
    if (
      event.ctrlKey
      && key === 'Enter'
    ) {
      event.preventDefault();

      if (keyboardSaleModalOpen()) {
        keyboardConfirmSale();
      }

      return;
    }


    /*
      ALT + cantidades
    */
    if (
      event.altKey
      && keyboardSaleModalOpen()
    ) {

      if (
        ['1', '2', '4', '6']
          .includes(key)
      ) {
        event.preventDefault();

        keyboardSetQuantity(
          Number(key)
        );

        return;
      }


      if (key === '0') {
        event.preventDefault();
        keyboardClearSearch();
        return;
      }
    }


    /*
      Funciones globales
    */
    switch (key) {

      case 'F2':
        event.preventDefault();
        keyboardNewSale();
        break;


      case 'F3':
        event.preventDefault();
        keyboardFocusSearch();
        break;


      case 'F4':
        event.preventDefault();
        keyboardAddProduct();
        break;


      case 'F6':
        event.preventDefault();
        keyboardFocusQuantity();
        break;


      case 'F7':
        event.preventDefault();

        if (keyboardSaleModalOpen()) {
          keyboardChangeQuantity(1);
        }

        break;


      case 'F8':
        event.preventDefault();

        if (keyboardSaleModalOpen()) {
          keyboardChangeQuantity(-1);
        }

        break;


      case 'F9':
        event.preventDefault();
        keyboardGoSales();
        break;


      case 'F10':
        event.preventDefault();
        keyboardCashAction();
        break;
    }

  }
);


/* ============================================================
   START
============================================================ */

document
  .querySelectorAll('.nav-item')
  .forEach(button => {
    button.onclick = () => {
      const targetView =
        button.dataset.view;

      if (targetView === 'purchases') {
        openPurchasesModule();
        return;
      }

      if (targetView === 'users') {
        openUsersModule();
        return;
      }

      if (targetView === 'audit') {
        openAuditModule();
        return;
      }

      render(targetView);
    };


    ensureAuditNavItem();

    if (currentView === 'audit') {
      bindAuditEvents();
    }


    refreshCurrentViewPagination();
  });

render();

syncFromApi();






















/* ============================================================
   USERS MODULE
============================================================ */

function userRoleLabel(role) {
  const labels = {
    ADMIN: 'Administrador',
    VENDEDOR: 'Vendedor'
  };

  return labels[role] || role;
}


async function loadUsers() {
  const response =
    await authenticatedFetch(
      `${API_BASE}/api/users`
    );

  const data =
    await response
      .json()
      .catch(() => []);

  if (!response.ok) {
    throw new Error(
      data.detail ||
      'No fue posible cargar los usuarios.'
    );
  }

  state.users =
    Array.isArray(data)
      ? data
      : [];
}

async function openUsersModule() {
  if (
    state.currentUser?.role !== 'ADMIN'
  ) {
    toast(
      'Este módulo es exclusivo de administradores.'
    );

    return;
  }

  try {
    await loadUsers();

    render('users');

  } catch (error) {
    toast(
      error.message
    );
  }
}








function usersView() {
  const manageableUsers =
    state.users.filter(
      user =>
        user.role === 'ADMIN' ||
        user.role === 'VENDEDOR'
    );

  const activeUsers =
    manageableUsers.filter(
      user => user.active
    ).length;

  const inactiveUsers =
    manageableUsers.filter(
      user => !user.active
    ).length;

  return `
    <div class="grid metrics users-metrics">

      <div class="card metric">
        <span class="label">
          Usuarios operativos
        </span>

        <div class="value">
          ${manageableUsers.length}
        </div>

        <span class="delta positive">
          Caja y operación
        </span>
      </div>


      <div class="card metric">
        <span class="label">
          Activos
        </span>

        <div class="value">
          ${activeUsers}
        </div>

        <span class="delta positive">
          Con acceso al sistema
        </span>
      </div>


      <div class="card metric">
        <span class="label">
          Desactivados
        </span>

        <div class="value">
          ${inactiveUsers}
        </div>

        <span
          class="delta ${inactiveUsers
      ? 'negative'
      : 'positive'
    }"
        >
          Sin acceso
        </span>
      </div>

    </div>


    <div class="grid users-layout">

      <section class="card">

        <div class="card-head">
          <div>
            <p class="eyebrow">
              ADMINISTRACIÓN
            </p>

            <h2>
              Crear usuario
            </h2>
          </div>
        </div>


        <form
          id="create-user-form"
          class="users-form"
        >

          <label>
            <span>
              Nombre completo
            </span>

            <input
              class="input"
              id="user-full-name"
              type="text"
              minlength="2"
              maxlength="160"
              placeholder="Ej. Juan Pérez"
              required
            />
          </label>


          <label>
            <span>
              Usuario
            </span>

            <input
              class="input"
              id="user-username"
              type="text"
              minlength="3"
              maxlength="80"
              placeholder="Ej. juan"
              autocomplete="off"
              required
            />
          </label>


          <label>
            <span>
              Contraseña inicial
            </span>

            <input
              class="input"
              id="user-password"
              type="password"
              minlength="6"
              placeholder="Mínimo 6 caracteres"
              autocomplete="new-password"
              required
            />
          </label>


          <label>
            <span>
              Rol
            </span>

            <select
              class="input"
              id="user-role"
              required
            >
              <option value="VENDEDOR">
                Vendedor
              </option>

              <option value="ADMIN">
                Administrador
              </option>
            </select>
          </label>


          <div class="users-role-info">

            <strong>
              Permisos
            </strong>

            <p>
              Caja puede registrar ventas y
              manejar apertura/cierre de caja.
            </p>

            <p>
              Operación puede consultar y
              ajustar inventario.
            </p>

          </div>


          <button
            type="submit"
            class="btn"
            id="create-user-submit"
          >
            + Crear usuario
          </button>

        </form>

      </section>


      <section class="card users-list-card">

        <div class="card-head">

          <div>
            <p class="eyebrow">
              PERSONAL
            </p>

            <h2>
              Usuarios
            </h2>
          </div>


          <button
            type="button"
            class="btn secondary"
            id="refresh-users"
          >
            Actualizar
          </button>

        </div>

        <div class="users-toolbar">

          <input
            class="input"
            id="users-search"
            type="search"
            placeholder="Buscar por nombre o usuario…"
            autocomplete="off"
          />

          <select
            class="input"
            id="users-role-filter"
          >
            <option value="all">
              Todos los roles
            </option>

            <option value="VENDEDOR">
              Vendedor
            </option>

            <option value="ADMIN">
              Administrador
            </option>
          </select>

          <select
            class="input"
            id="users-status-filter"
          >
            <option value="all">
              Todos los estados
            </option>

            <option value="active">
              Activos
            </option>

            <option value="inactive">
              Desactivados
            </option>
          </select>

        </div>


        <div class="users-list">

          ${manageableUsers.length
      ? manageableUsers.map(
        user => `
                    <article
                      class="user-item"
                      data-user-search="${(
            `${user.full_name || ''} ${user.username || ''}`
          ).toLowerCase()}"
                      data-user-role="${user.role}"
                      data-user-status="${user.active ? 'active' : 'inactive'}"
                    >

                      <div
                        class="user-avatar"
                      >
                        ${getUserInitials(
            user.full_name
          )}
                      </div>


                      <div
                        class="user-main"
                      >

                        <div
                          class="user-name-row"
                        >
                          <strong>
                            ${user.full_name}
                          </strong>

                          <span
                            class="pill ${user.active
            ? 'green'
            : 'yellow'
          }"
                          >
                            ${user.active
            ? 'Activo'
            : 'Desactivado'
          }
                          </span>
                        </div>


                        <small>
                          @${user.username}
                          ·
                          ${userRoleLabel(
            user.role
          )}
                        </small>

                      </div>


                      <div
                        class="user-actions"
                      >

                        ${user.active
            ? `
                              <button
                                type="button"
                                class="
                                  btn
                                  secondary
                                  user-delete-btn
                                "
                                data-user-id="${user.id}"
                                data-user-name="${user.full_name}"
                              >
                                Desactivar usuario
                              </button>
                            `
            : `
                              <button
                                type="button"
                                class="
                                  btn
                                  secondary
                                  user-reactivate-btn
                                "
                                data-user-id="${user.id}"
                              >
                                Reactivar
                              </button>
                            `
          }

                      </div>

                    </article>
                  `
      ).join('')
      : `
                  <div class="empty">
                    No hay usuarios de caja
                    u operación.
                  </div>
                `
    }

          <div
            class="empty"
            id="users-filter-empty"
            style="display:none"
          >
            No se encontraron usuarios con esos filtros.
          </div>

        </div>

      </section>

    </div>

    

  `;
}


function filterUsersModule() {
  const search =
    document
      .querySelector('#users-search')
      ?.value
      .trim()
      .toLowerCase()
    || '';

  const role =
    document
      .querySelector('#users-role-filter')
      ?.value
    || 'all';

  const status =
    document
      .querySelector('#users-status-filter')
      ?.value
    || 'all';

  const rows = [
    ...document.querySelectorAll(
      '.user-item'
    )
  ];

  let visible = 0;

  rows.forEach(row => {
    const matchesSearch =
      !search ||
      (row.dataset.userSearch || '')
        .includes(search);

    const matchesRole =
      role === 'all' ||
      row.dataset.userRole === role;

    const matchesStatus =
      status === 'all' ||
      row.dataset.userStatus === status;

    const matches =
      matchesSearch &&
      matchesRole &&
      matchesStatus;

    row.style.display =
      matches ? '' : 'none';

    if (matches) {
      visible += 1;
    }
  });

  const empty =
    document.querySelector(
      '#users-filter-empty'
    );

  if (empty) {
    empty.style.display =
      visible === 0
        ? ''
        : 'none';
  }
}


async function createOperationalUser(
  event
) {
  event.preventDefault();

  const submit =
    document.querySelector(
      '#create-user-submit'
    );

  const payload = {
    full_name:
      document
        .querySelector(
          '#user-full-name'
        )
        ?.value
        .trim(),

    username:
      document
        .querySelector(
          '#user-username'
        )
        ?.value
        .trim()
        .toLowerCase(),

    password:
      document
        .querySelector(
          '#user-password'
        )
        ?.value,

    role:
      document
        .querySelector(
          '#user-role'
        )
        ?.value
  };


  if (
    payload.role !== 'VENDEDOR' &&
    payload.role !== 'ADMIN'
  ) {
    toast(
      'Rol no permitido.'
    );

    return;
  }


  if (submit) {
    submit.disabled = true;

    submit.textContent =
      'Creando…';
  }


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/users`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify(
              payload
            )
        }
      );


    const data =
      await response
        .json()
        .catch(
          () => ({})
        );


    if (!response.ok) {
      throw new Error(
        data.detail ||
        'No fue posible crear el usuario.'
      );
    }


    toast(
      `Usuario ${data.username} creado correctamente.`
    );

    await loadUsers();

    render('users');


  } catch (error) {

    toast(
      error.message
    );

  } finally {

    if (submit) {
      submit.disabled = false;

      submit.textContent =
        '+ Crear usuario';
    }
  }
}


async function deleteOperationalUser(
  userId,
  userName
) {
  const confirmed =
    window.confirm(
      `¿Desactivar el usuario "${userName}"?\n\n` +
      'El usuario no podrá iniciar sesión, ' +
      'pero su registro se conservará.'
    );

  if (!confirmed) {
    return;
  }


  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/users/${userId}`,
        {
          method: 'DELETE'
        }
      );


    const data =
      await response
        .json()
        .catch(
          () => ({})
        );


    if (!response.ok) {
      throw new Error(
        data.detail ||
        'No fue posible eliminar el usuario.'
      );
    }


    toast(
      `${userName} fue desactivado correctamente.`
    );

    await loadUsers();

    render('users');


  } catch (error) {

    toast(
      error.message
    );
  }
}


async function reactivateOperationalUser(
  userId
) {
  try {

    const response =
      await authenticatedFetch(
        `${API_BASE}/api/users/${userId}/active`,
        {
          method: 'PATCH',

          headers: {
            'Content-Type':
              'application/json'
          },

          body:
            JSON.stringify({
              active: true
            })
        }
      );


    const data =
      await response
        .json()
        .catch(
          () => ({})
        );


    if (!response.ok) {
      throw new Error(
        data.detail ||
        'No fue posible reactivar el usuario.'
      );
    }


    toast(
      'Usuario reactivado.'
    );

    await loadUsers();

    render('users');


  } catch (error) {

    toast(
      error.message
    );
  }
}


function bindUsersModuleEvents() {

  document
    .querySelector('#users-search')
    ?.addEventListener(
      'input',
      filterUsersModule
    );

  document
    .querySelector('#users-role-filter')
    ?.addEventListener(
      'change',
      filterUsersModule
    );

  document
    .querySelector('#users-status-filter')
    ?.addEventListener(
      'change',
      filterUsersModule
    );

  document
    .querySelector(
      '#create-user-form'
    )
    ?.addEventListener(
      'submit',
      createOperationalUser
    );


  document
    .querySelector(
      '#refresh-users'
    )
    ?.addEventListener(
      'click',
      async () => {

        try {
          await loadUsers();

          render('users');

        } catch (error) {
          toast(
            error.message
          );
        }
      }
    );


  document
    .querySelectorAll(
      '.user-delete-btn'
    )
    .forEach(button => {

      button.addEventListener(
        'click',
        () => {

          deleteOperationalUser(
            Number(
              button.dataset.userId
            ),
            button.dataset.userName
          );

        }
      );

    });


  document
    .querySelectorAll(
      '.user-reactivate-btn'
    )
    .forEach(button => {

      button.addEventListener(
        'click',
        () => {

          reactivateOperationalUser(
            Number(
              button.dataset.userId
            )
          );

        }
      );

    });
}


/* agregar vista dinámicamente */
views.users = {
  title: 'Usuarios',
  render: usersView
};




/* ============================================================
   AUTH STARTUP
============================================================ */



// ============================================================
// login-password-toggle-handler
// ============================================================

document.addEventListener(
  'click',
  event => {

    const button =
      event.target.closest(
        '#toggle-login-password'
      );

    if (!button) {
      return;
    }

    const input =
      document.querySelector(
        '#login-screen input[type="password"], #login-screen input[data-login-password], input[name="password"]'
      )
      || document.querySelector(
        '.password-field input'
      );

    if (!input) {
      return;
    }

    const showing =
      input.type === 'text';

    input.type =
      showing
        ? 'password'
        : 'text';

    button.textContent =
      showing
        ? 'Ver'
        : 'Ocultar';

    button.setAttribute(
      'aria-label',
      showing
        ? 'Mostrar contraseña'
        : 'Ocultar contraseña'
    );

    button.title =
      showing
        ? 'Mostrar contraseña'
        : 'Ocultar contraseña';
  }
);


initializeAuthentication();

