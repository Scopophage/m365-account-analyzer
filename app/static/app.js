const $ = (id) => document.getElementById(id);

let lastBatchRows = [];
let lastBatchIdentifiers = [];
let lastAccountIdentifier = null;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '<span class="muted">—</span>';
  if (Array.isArray(value)) return escapeHtml(value.join(', '));
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';
  return escapeHtml(value);
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return date.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
}

function statusClass(status) {
  const s = String(status || '').toLowerCase();
  if (s.includes('actif confirme') || s.includes('actif confirmé') || s.includes('actif non') || s.includes('boite exchange active') || s.includes('boîte exchange active') || s.includes('boite partagee exchange active') || s.includes('boîte partagée exchange active')) return 'success';
  if (s.includes('critique') || s.includes('privilege') || s.includes('privilège')) return 'danger';
  if (s.includes('desactive') || s.includes('désactivé')) return 'neutral';
  if (s.includes('confirmer') || s.includes('revue') || s.includes('surveiller') || s.includes('dormant') || s.includes('technique') || s.includes('partagee') || s.includes('partagée') || s.includes('objet mail')) return 'warning';
  return 'neutral';
}

function riskClass(risk) {
  const r = String(risk || '').toLowerCase();
  if (r.includes('eleve') || r.includes('élevé')) return 'danger';
  if (r.includes('moyen')) return 'warning';
  if (r.includes('faible')) return 'success';
  return 'neutral';
}

function showStatus(message, type = 'info') {
  const panel = $('statusPanel');
  panel.className = `status-panel ${type}`;
  panel.innerHTML = message;
  panel.classList.remove('hidden');
}

function hideStatus() {
  $('statusPanel').classList.add('hidden');
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!response.ok) {
    const extra = data.details ? `\n${JSON.stringify(data.details).slice(0, 1200)}` : '';
    throw new Error((data.error || data.detail || `Erreur HTTP ${response.status}`) + extra);
  }
  return data;
}

function renderKv(items) {
  return `<div class="kv">${items.map(([key, value, cssClass]) => `
    <div class="key">${escapeHtml(key)}</div>
    <div class="value ${cssClass || ''}">${value}</div>
  `).join('')}</div>`;
}

function renderPills(items) {
  const pills = items.filter(Boolean).map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join('');
  return pills ? `<div class="pill-row">${pills}</div>` : '';
}

function renderDiagnostics(data) {
  const tests = data.tests || [];
  const rows = tests.map((test) => {
    const ok = test.ok === true ? 'OK' : test.ok === null ? 'Ignore' : 'Erreur';
    const cls = test.ok === true ? 'success' : test.ok === null ? 'neutral' : 'danger';
    return `
      <div class="diagnostic-item">
        <div class="diagnostic-title"><span class="badge ${cls}">${ok}</span>${escapeHtml(test.name)}</div>
        <div class="muted">${escapeHtml(test.detail || '')}</div>
      </div>
    `;
  }).join('');

  const missing = data.missingEnv?.length ? `<p><strong>Variables manquantes :</strong> ${escapeHtml(data.missingEnv.join(', '))}</p>` : '';
  showStatus(`
    <strong>Diagnostic configuration</strong>
    ${missing}
    <p>Période rapports : <strong>${escapeHtml(data.graphPeriod)}</strong> · Reports activés : <strong>${displayValue(data.reportsEnabled)}</strong> · Cache : <strong>${escapeHtml(data.cacheHours)} h</strong></p>
    <p>Exchange Online : <strong>${displayValue(data.exchangeEnabled)}</strong> · Auth : <strong>${escapeHtml(data.exchangeAuthMode || '—')}</strong> · Organisation : <strong>${escapeHtml(data.exchangeOrganization || '—')}</strong></p>
    <div class="diagnostic-list">${rows}</div>
  `, data.status === 'ok' ? 'ok' : data.status === 'partial' ? 'partial' : 'error');
}

function renderResult(data) {
  const identity = data.identity || {};
  const onprem = identity.onPremises || {};
  const conclusion = data.conclusion || {};
  const licenses = data.licenses || {};
  const activity = data.m365Activity || {};
  const exchange = data.exchange || {};
  const memberships = data.memberships || {};
  const security = data.security || {};
  const ownership = data.ownership || {};
  const manager = ownership.manager || {};
  const sign = data.signInActivity || {};
  const latest = conclusion.latestSignal || {};
  const sourceCoverage = data.sourceCoverage || {};

  const licenseItems = (licenses.items || []).map((lic) =>
    `<li>${escapeHtml(lic.skuPartNumber || lic.skuId || 'Licence inconnue')}</li>`
  ).join('') || '<li>Pas de licence affectee ou permission insuffisante</li>';

  const productsFromReport = (licenses.assignedProductsFromReport || []).map((product) =>
    `<li>${escapeHtml(product)}</li>`
  ).join('');

  const proxyAddresses = (identity.proxyAddresses || []).slice(0, 50).map((alias) => `<li class="mono">${escapeHtml(alias)}</li>`).join('');
  const authMethodRows = (security.methods || []).map((m) => `
    <tr><td>${displayValue(m.display || m.label)}</td><td class="mono">${displayValue(m.type)}</td></tr>
  `).join('');
  const ownedAppRows = (ownership.ownedApplications || []).map((o) => `
    <tr><td>${displayValue(o.displayName)}</td><td class="mono">${displayValue(o.appId || o.id)}</td></tr>
  `).join('');

  const groupRows = (memberships.groups || []).slice(0, 30).map((g) => `
    <tr>
      <td>${escapeHtml(g.displayName || '')}</td>
      <td>${displayValue(g.mail)}</td>
      <td>${displayValue(g.securityEnabled)}</td>
      <td>${displayValue((g.groupTypes || []).join(', ') || g.type)}</td>
      <td>${displayValue(g.importance)}</td>
    </tr>
  `).join('');

  const roleRows = [
    ...(memberships.directoryRoles || []).map((r) => ({...r, scope: 'Direct'})),
    ...(memberships.transitiveDirectoryRoles || []).map((r) => ({...r, scope: 'Transitif'})),
  ].map((r) => `
    <tr><td>${escapeHtml(r.displayName || '')}</td><td>${escapeHtml(r.scope || '')}</td><td class="mono">${escapeHtml(r.id || '')}</td></tr>
  `).join('');

  const signinRows = (data.recentSignIns || []).map((s) => `
    <tr>
      <td>${formatDate(s.createdDateTime)}</td>
      <td>${displayValue(s.appDisplayName)}</td>
      <td>${displayValue(s.resourceDisplayName)}</td>
      <td>${displayValue(s.clientAppUsed)}</td>
      <td>${displayValue(s.isInteractive)}</td>
      <td>${displayValue(s.statusCode === 0 ? 'Succes' : s.statusFailureReason || s.statusCode)}</td>
      <td>${displayValue(s.ipAddress)}</td>
      <td>${displayValue([s.city, s.countryOrRegion].filter(Boolean).join(', '))}</td>
    </tr>
  `).join('');

  const signalRows = (data.signals || []).map((s) => `
    <tr>
      <td>${escapeHtml(s.name || '')}</td>
      <td>${formatDate(s.date)}</td>
      <td>${displayValue(s.daysAgo)}</td>
      <td>${escapeHtml(s.source || '')}</td>
    </tr>
  `).join('');

  const warningList = (data.warnings || []).map((w) => `<li>${escapeHtml(w)}</li>`).join('');
  const reasonList = (conclusion.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join('');

  const coveragePills = renderPills([
    sourceCoverage.graphUser ? 'User Graph OK' : 'User Graph indisponible',
    sourceCoverage.memberOf ? 'Groupes lus' : 'Groupes absents/non lus',
    sourceCoverage.transitiveMemberOf ? 'Roles transitifs lus' : 'Roles transitifs absents/non lus',
    sourceCoverage.authenticationMethods ? 'MFA lisible' : 'MFA non lisible',
    sourceCoverage.manager ? 'Manager lu' : 'Manager absent/non lu',
    sourceCoverage.signInLogs ? 'Sign-ins disponibles' : 'Sign-ins non disponibles',
    sourceCoverage.subscribedSkus ? 'Licences tenant lisibles' : 'Licences tenant non lues',
    sourceCoverage.office365ActiveUserDetail ? 'Rapport M365 trouvé' : 'Rapport M365 sans ligne',
    sourceCoverage.exchangeOnline ? 'Exchange Online trouvé' : (exchange.enabled ? 'Exchange Online sans objet' : 'Exchange Online désactivé'),
  ]);

  const html = `
    <div class="result-header">
      <div>
        <h2>Résultat : ${escapeHtml(identity.displayName || data.searchedIdentifier)}</h2>
        <div class="result-subtitle mono">${escapeHtml(identity.userPrincipalName || '')}</div>
      </div>
      <div class="pill-row">
        <span class="badge ${statusClass(conclusion.status)}">${escapeHtml(conclusion.status || 'Non calcule')}</span>
        <span class="badge ${riskClass(conclusion.riskLevel)}">Risque : ${escapeHtml(conclusion.riskLevel || '—')}</span>
        <span class="badge neutral">Confiance : ${escapeHtml(conclusion.confidence || '—')}</span>
      </div>
    </div>

    <div class="grid summary-grid">
      <div class="card span-2">
        <h3>Conclusion</h3>
        ${renderKv([
          ['Score', displayValue(conclusion.score)],
          ['Privilegie', displayValue(conclusion.isPrivileged)],
          ['MFA detecte', displayValue(conclusion.hasMfaMethod)],
          ['Dernier signal', latest.date ? formatDate(latest.date) : '—'],
          ['Jours depuis dernier signal', displayValue(conclusion.latestSignalDaysAgo)],
          ['Technique probable', displayValue(conclusion.isTechnicalCandidate)],
          ['Critique potentiel', displayValue(conclusion.isCriticalCandidate)],
          ['Resume', displayValue(conclusion.usageSummary)],
        ])}
        <h4>Recommandation</h4>
        <p>${escapeHtml(conclusion.recommendation || '')}</p>
        <ul class="reason-list">${reasonList}</ul>
      </div>

      <div class="card">
        <h3>Identité</h3>
        ${renderKv([
          ['Nom', displayValue(identity.displayName)],
          ['UPN', displayValue(identity.userPrincipalName), 'mono'],
          ['Mail', displayValue(identity.mail), 'mono'],
          ['Type', displayValue(identity.userType)],
          ['Service', displayValue(identity.department)],
          ['Titre', displayValue(identity.jobTitle)],
          ['Employee type', displayValue(identity.employeeType)],
          ['Employee ID', displayValue(identity.employeeId), 'mono'],
          ['Id objet', displayValue(identity.id), 'mono'],
        ])}
      </div>

      <div class="card">
        <h3>Sécurité / cycle de vie</h3>
        ${renderKv([
          ['Compte activé', displayValue(identity.accountEnabled)],
          ['Créé le', formatDate(identity.createdDateTime)],
          ['Mot de passe changé', formatDate(identity.lastPasswordChangeDateTime)],
          ['Password policies', displayValue(identity.passwordPolicies)],
          ['Company', displayValue(identity.companyName)],
          ['Bureau', displayValue(identity.officeLocation)],
        ])}
      </div>


      <div class="card">
        <h3>MFA / privilèges</h3>
        ${renderKv([
          ['MFA détecté', displayValue(security.hasMfaMethod)],
          ['Méthodes lisibles', displayValue(security.methodsReadable)],
          ['Nb méthodes', displayValue(security.methodsCount)],
          ['Compte privilégié', displayValue(security.isPrivileged)],
          ['Rôles privilégiés', displayValue((security.privilegedRoles || []).join(', '))],
        ])}
        <p class="hint">${escapeHtml(security.mfaRecommendation || '')}</p>
      </div>

      <div class="card">
        <h3>Propriétaire probable</h3>
        ${renderKv([
          ['Manager', displayValue(manager.displayName)],
          ['Manager UPN', displayValue(manager.userPrincipalName), 'mono'],
          ['Service', displayValue(ownership.department)],
          ['Société', displayValue(ownership.companyName)],
          ['Bureau', displayValue(ownership.officeLocation)],
          ['Propriétaire probable', displayValue(ownership.probableOwner)],
          ['Objets possédés', displayValue(ownership.ownedObjectsCount)],
        ])}
      </div>

      <div class="card span-2">
        <h3>Synchronisation on-premise</h3>
        ${renderKv([
          ['Synchronisé AD', displayValue(onprem.syncEnabled)],
          ['SamAccountName', displayValue(onprem.samAccountName), 'mono'],
          ['Dernière synchro', formatDate(onprem.lastSyncDateTime)],
          ['Domaine', displayValue(onprem.domainName), 'mono'],
          ['UPN on-prem', displayValue(onprem.userPrincipalName), 'mono'],
          ['DN', displayValue(onprem.distinguishedName), 'mono'],
        ])}
      </div>

      <div class="card">
        <h3>Sign-in activity</h3>
        ${renderKv([
          ['Dernière réussie', formatDate(sign.lastSuccessfulSignInDateTime)],
          ['Interactive', formatDate(sign.lastSignInDateTime)],
          ['Non interactive', formatDate(sign.lastNonInteractiveSignInDateTime)],
        ])}
      </div>

      <div class="card">
        <h3>Activité Microsoft 365</h3>
        ${activity.found ? renderKv([
          ['Rapport actualisé', displayValue(activity.reportRefreshDate)],
          ['Exchange', displayValue(activity.exchangeLastActivityDate)],
          ['OneDrive', displayValue(activity.oneDriveLastActivityDate)],
          ['SharePoint', displayValue(activity.sharePointLastActivityDate)],
          ['Teams', displayValue(activity.teamsLastActivityDate)],
        ]) : `<p>${escapeHtml(activity.reportStatus || 'Aucune ligne trouvée dans le rapport Graph Reports pour cet utilisateur.')}</p>`}
      </div>

      <div class="card span-2">
        <h3>Exchange Online</h3>
        ${exchange.enabled ? renderKv([
          ['Objet trouvé', displayValue(exchange.found || exchange.recipientFound)],
          ['Type destinataire', displayValue(exchange.recipientTypeDetails)],
          ['Boîte aux lettres', displayValue(exchange.hasMailbox)],
          ['Boîte partagée', displayValue(exchange.isSharedMailbox)],
          ['Salle / équipement', displayValue(exchange.isRoomMailbox || exchange.isEquipmentMailbox)],
          ['SMTP principal', displayValue(exchange.primarySmtpAddress), 'mono'],
          ['Masqué GAL', displayValue(exchange.hiddenFromAddressLists)],
          ['Dernière action utilisateur', formatDate(exchange.lastUserActionTime)],
          ['Dernier logon boîte', formatDate(exchange.lastLogonTime)],
          ['Taille', displayValue(exchange.totalItemSize)],
          ['Éléments', displayValue(exchange.itemCount)],
          ['Full Access', displayValue(exchange.fullAccessCount)],
          ['Send As', displayValue(exchange.sendAsCount)],
          ['Send on behalf', displayValue(exchange.sendOnBehalfCount)],
        ]) : '<p>Exchange Online désactivé dans la configuration.</p>'}
        ${exchange.error ? `<p class="hint danger-text">${escapeHtml(exchange.error)}</p>` : ''}
        ${exchange.fromCache ? '<p class="hint">Résultat Exchange lu depuis le cache local.</p>' : ''}
      </div>

      <div class="card">
        <h3>Licences</h3>
        ${renderKv([
          ['Nombre', displayValue(licenses.count)],
          ['Exchange', displayValue(licenses.hasExchangeLicense)],
          ['OneDrive', displayValue(licenses.hasOneDriveLicense)],
          ['SharePoint', displayValue(licenses.hasSharePointLicense)],
          ['Teams', displayValue(licenses.hasTeamsLicense)],
        ])}
        <ul class="small-list">${licenseItems}</ul>
        ${productsFromReport ? `<h4>Produits du rapport</h4><ul class="small-list">${productsFromReport}</ul>` : ''}
      </div>

      <div class="card span-2">
        <h3>Couverture des sources</h3>
        ${coveragePills}
        <p class="hint">Ces pastilles indiquent seulement si la source a retourne de la donnee exploitable pour ce compte.</p>
      </div>

      ${proxyAddresses ? `<div class="card span-2"><h3>Alias / proxyAddresses</h3><ul class="small-list">${proxyAddresses}</ul></div>` : ''}

      ${exchange.enabled && exchange.hasMailbox ? `<div class="card span-2"><h3>Délégations Exchange</h3>
        <div class="delegation-grid">
          <div><h4>Full Access (${displayValue(exchange.fullAccessCount)})</h4><ul class="small-list">${(exchange.fullAccess || []).map((x) => `<li>${escapeHtml(x.user || '')} <span class="muted">${escapeHtml((x.accessRights || []).join(', '))}</span></li>`).join('') || '<li>Aucune délégation Full Access lue.</li>'}</ul></div>
          <div><h4>Send As (${displayValue(exchange.sendAsCount)})</h4><ul class="small-list">${(exchange.sendAs || []).map((x) => `<li>${escapeHtml(x.trustee || '')} <span class="muted">${escapeHtml((x.accessRights || []).join(', '))}</span></li>`).join('') || '<li>Aucune délégation Send As lue.</li>'}</ul></div>
          <div><h4>Send on behalf (${displayValue(exchange.sendOnBehalfCount)})</h4><ul class="small-list">${(exchange.sendOnBehalfTo || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Aucune délégation Send on behalf lue.</li>'}</ul></div>
        </div>
      </div>` : ''}

      <div class="card span-2">
        <h3>Méthodes MFA / authentification</h3>
        <div class="table-wrap"><table><thead><tr><th>Méthode</th><th>Type Graph</th></tr></thead><tbody>${authMethodRows || '<tr><td colspan="2">Aucune méthode lisible ou permission insuffisante.</td></tr>'}</tbody></table></div>
      </div>

      <div class="card span-2">
        <h3>Objets possédés / applications</h3>
        <div class="table-wrap"><table><thead><tr><th>Nom</th><th>AppId / Id</th></tr></thead><tbody>${ownedAppRows || '<tr><td colspan="2">Aucune application possédée trouvée ou permission insuffisante.</td></tr>'}</tbody></table></div>
      </div>
    </div>

    <div class="card">
      <h3>Signaux exploités</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Signal</th><th>Date</th><th>Jours</th><th>Source</th></tr></thead>
          <tbody>${signalRows || '<tr><td colspan="4">Aucun signal.</td></tr>'}</tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h3>Groupes directs (${displayValue(memberships.groupsCount)})</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Nom</th><th>Mail</th><th>Sécurité</th><th>Type</th><th>Importance</th></tr></thead>
          <tbody>${groupRows || '<tr><td colspan="5">Aucun groupe direct ou permission insuffisante.</td></tr>'}</tbody>
        </table>
      </div>
      ${(memberships.groupsCount || 0) > 30 ? '<p class="hint">Affichage limité aux 30 premiers groupes.</p>' : ''}
    </div>

    <div class="card">
      <h3>Rôles d'annuaire (${displayValue(memberships.allDirectoryRolesCount || memberships.directoryRolesCount)})</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Rôle</th><th>Portée</th><th>Id</th></tr></thead>
          <tbody>${roleRows || '<tr><td colspan="3">Aucun rôle direct ou transitif détecté.</td></tr>'}</tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h3>Derniers sign-ins disponibles</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Date</th><th>Application</th><th>Ressource</th><th>Client</th><th>Interactif</th><th>Statut</th><th>IP</th><th>Lieu</th></tr></thead>
          <tbody>${signinRows || '<tr><td colspan="8">Aucun sign-in récent disponible ou permission insuffisante.</td></tr>'}</tbody>
        </table>
      </div>
    </div>

    ${warningList ? `<div class="card"><h3>Avertissements</h3><ul class="warning-list">${warningList}</ul></div>` : ''}

    <div class="card">
      <h3>Note de périmètre</h3>
      <p>${escapeHtml(conclusion.tenantOnlyWarning || '')}</p>
    </div>
  `;

  const result = $('result');
  result.innerHTML = html;
  result.classList.remove('hidden');
  result.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

async function analyzeIdentifier(identifier) {
  showStatus('Analyse en cours...', 'info');
  const data = await fetchJson(`/api/account?identifier=${encodeURIComponent(identifier)}`);
  hideStatus();
  lastAccountIdentifier = identifier;
  const pdfBtn = $('exportAccountPdfBtn');
  if (pdfBtn) pdfBtn.disabled = false;
  renderResult(data);
  return data;
}

function toBatchRows(results) {
  return results.map((item) => {
    if (!item.ok) {
      return {
        identifier: item.identifier,
        ok: 'non',
        name: '',
        upn: '',
        status: '',
        score: '',
        confidence: '',
        risk: '',
        lastSignal: '',
        lastSignalDays: '',
        technical: '',
        privileged: '',
        mfa: '',
        exchangeType: '',
        sharedMailbox: '',
        exchangeDelegations: '',
        owner: '',
        recommendation: '',
        error: item.error || 'Erreur inconnue',
      };
    }
    const result = item.result || item;
    const identity = result.identity || {};
    const conclusion = result.conclusion || {};
    const security = result.security || {};
    const ownership = result.ownership || {};
    const exchange = result.exchange || {};
    return {
      identifier: item.identifier || result.searchedIdentifier,
      ok: 'oui',
      name: identity.displayName || '',
      upn: identity.userPrincipalName || '',
      status: conclusion.status || '',
      score: conclusion.score ?? '',
      confidence: conclusion.confidence || '',
      risk: conclusion.riskLevel || '',
      lastSignal: conclusion.latestSignal?.date || '',
      lastSignalDays: conclusion.latestSignalDaysAgo ?? '',
      technical: conclusion.isTechnicalCandidate ? 'oui' : 'non',
      privileged: conclusion.isPrivileged ? 'oui' : 'non',
      mfa: conclusion.hasMfaMethod ? 'oui' : 'non',
      exchangeType: exchange.recipientTypeDetails || '',
      sharedMailbox: exchange.isSharedMailbox ? 'oui' : 'non',
      exchangeDelegations: exchange.delegationsFound ? 'oui' : 'non',
      owner: ownership.probableOwner || ownership.manager?.displayName || '',
      recommendation: conclusion.recommendation || '',
      error: '',
    };
  });
}

function renderBatch(rows) {
  lastBatchRows = rows;
  $('exportBatchBtn').disabled = rows.length === 0;
  $('exportExcelBtn').disabled = rows.length === 0;
  if ($('exportBatchPdfBtn')) $('exportBatchPdfBtn').disabled = rows.length === 0;
  const body = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.identifier)}</td>
      <td>${escapeHtml(r.ok)}</td>
      <td>${escapeHtml(r.name)}</td>
      <td class="mono">${escapeHtml(r.upn)}</td>
      <td><span class="badge ${statusClass(r.status)}">${escapeHtml(r.status)}</span></td>
      <td>${escapeHtml(r.score)}</td>
      <td>${escapeHtml(r.confidence)}</td>
      <td>${escapeHtml(r.risk)}</td>
      <td>${formatDate(r.lastSignal)}</td>
      <td>${escapeHtml(r.lastSignalDays)}</td>
      <td>${escapeHtml(r.technical)}</td>
      <td>${escapeHtml(r.privileged)}</td>
      <td>${escapeHtml(r.mfa)}</td>
      <td>${escapeHtml(r.exchangeType)}</td>
      <td>${escapeHtml(r.sharedMailbox)}</td>
      <td>${escapeHtml(r.exchangeDelegations)}</td>
      <td>${escapeHtml(r.owner)}</td>
      <td>${escapeHtml(r.recommendation)}</td>
      <td>${escapeHtml(r.error)}</td>
    </tr>
  `).join('');

  const summary = buildBatchSummary(rows);
  const panel = $('batchResult');
  panel.innerHTML = `
    <h2>Résultat analyse en lot</h2>
    <div class="dashboard-grid">
      ${dashboardCard('Analysés', summary.total)}
      ${dashboardCard('Actifs', summary.active)}
      ${dashboardCard('Dormants', summary.dormant)}
      ${dashboardCard('Techniques', summary.technical)}
      ${dashboardCard('Critiques', summary.critical)}
      ${dashboardCard('Privilégiés', summary.privileged)}
      ${dashboardCard('MFA détecté', summary.mfa)}
      ${dashboardCard('Boîtes Exchange', summary.exchangeMailboxes)}
      ${dashboardCard('Boîtes partagées', summary.sharedMailboxes)}
      ${dashboardCard('Délégations EXO', summary.exchangeDelegations)}
      ${dashboardCard('Erreurs', summary.errors)}
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Recherche</th><th>OK</th><th>Nom</th><th>UPN</th><th>Statut</th><th>Score</th><th>Confiance</th><th>Risque</th><th>Dernier signal</th><th>Jours</th><th>Technique</th><th>Privilégié</th><th>MFA</th><th>Exchange</th><th>Partagée</th><th>Délég.</th><th>Propriétaire</th><th>Recommandation</th><th>Erreur</th></tr></thead>
        <tbody>${body || '<tr><td colspan="13">Aucun résultat.</td></tr>'}</tbody>
      </table>
    </div>
  `;
  panel.classList.remove('hidden');
  panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

function dashboardCard(label, value) {
  return `<div class="metric-card"><div class="metric-value">${escapeHtml(value)}</div><div class="metric-label">${escapeHtml(label)}</div></div>`;
}

function buildBatchSummary(rows) {
  const norm = (v) => String(v || '').toLowerCase();
  return {
    total: rows.length,
    errors: rows.filter((r) => r.ok !== 'oui').length,
    active: rows.filter((r) => norm(r.status).includes('actif')).length,
    dormant: rows.filter((r) => norm(r.status).includes('dormant')).length,
    technical: rows.filter((r) => r.technical === 'oui').length,
    critical: rows.filter((r) => norm(r.status).includes('critique')).length,
    privileged: rows.filter((r) => r.privileged === 'oui').length,
    mfa: rows.filter((r) => r.mfa === 'oui').length,
    exchangeMailboxes: rows.filter((r) => r.exchangeType).length,
    sharedMailboxes: rows.filter((r) => r.sharedMailbox === 'oui').length,
    exchangeDelegations: rows.filter((r) => r.exchangeDelegations === 'oui').length,
  };
}

function downloadTextAsFile(text, filename, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function downloadCsv(rows) {
  const headers = ['identifier', 'ok', 'name', 'upn', 'status', 'score', 'confidence', 'risk', 'lastSignal', 'lastSignalDays', 'technical', 'privileged', 'mfa', 'exchangeType', 'sharedMailbox', 'exchangeDelegations', 'owner', 'recommendation', 'error'];
  const csv = [headers.join(';')].concat(rows.map((row) =>
    headers.map((header) => `"${String(row[header] ?? '').replaceAll('"', '""')}"`).join(';')
  )).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'm365_account_analyzer_batch.csv';
  a.click();
  URL.revokeObjectURL(url);
}

if ($('exportAccountPdfBtn')) {
  $('exportAccountPdfBtn').addEventListener('click', async () => {
    if (!lastAccountIdentifier) return showStatus('Analyse d abord une fiche compte.', 'error');
    showStatus('Generation du PDF fiche...', 'info');
    const response = await fetch(`/api/account/pdf?identifier=${encodeURIComponent(lastAccountIdentifier)}`);
    if (!response.ok) {
      const text = await response.text();
      return showStatus(`<pre>${escapeHtml(text)}</pre>`, 'error');
    }
    const blob = await response.blob();
    downloadBlob(blob, 'm365_account_analyzer_fiche.pdf');
    hideStatus();
  });
}

if ($('exportBatchPdfBtn')) {
  $('exportBatchPdfBtn').addEventListener('click', async () => {
    if (!lastBatchIdentifiers.length) return showStatus('L export PDF lot est disponible apres analyse d une liste ou d un fichier.', 'error');
    const form = new FormData();
    form.append('file', new Blob([lastBatchIdentifiers.join('\n')], { type: 'text/plain' }), 'batch.txt');
    showStatus('Generation du PDF lot...', 'info');
    const response = await fetch('/api/batch/export-pdf', { method: 'POST', body: form });
    if (!response.ok) {
      const text = await response.text();
      return showStatus(`<pre>${escapeHtml(text)}</pre>`, 'error');
    }
    const blob = await response.blob();
    downloadBlob(blob, 'm365_account_analyzer_export.pdf');
    hideStatus();
  });
}

$('searchBtn').addEventListener('click', async () => {
  const identifier = $('identifierInput').value.trim();
  if (!identifier) return showStatus('Saisis un identifiant.', 'error');
  try {
    await analyzeIdentifier(identifier);
  } catch (error) {
    showStatus(`<pre>${escapeHtml(error.message)}</pre>`, 'error');
  }
});

$('identifierInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') $('searchBtn').click();
});

$('healthBtn').addEventListener('click', async () => {
  showStatus('Diagnostic Graph en cours...', 'info');
  try {
    const data = await fetchJson('/api/diagnostics');
    renderDiagnostics(data);
  } catch (error) {
    showStatus(`<pre>${escapeHtml(error.message)}</pre>`, 'error');
  }
});

$('batchBtn').addEventListener('click', async () => {
  const identifiers = $('batchText').value.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  if (!identifiers.length) return showStatus('Colle au moins un identifiant.', 'error');
  lastBatchIdentifiers = identifiers;
  showStatus(`Analyse de ${identifiers.length} compte(s)...`, 'info');
  const results = [];
  for (const identifier of identifiers.slice(0, 200)) {
    try {
      const result = await fetchJson(`/api/account?identifier=${encodeURIComponent(identifier)}`);
      results.push({ identifier, ok: true, result });
    } catch (error) {
      results.push({ identifier, ok: false, error: error.message });
    }
  }
  hideStatus();
  renderBatch(toBatchRows(results));
});

$('csvBtn').addEventListener('click', async () => {
  const file = $('csvFile').files[0];
  if (!file) return showStatus('Choisis un fichier CSV ou TXT.', 'error');
  const form = new FormData();
  form.append('file', file);
  showStatus('Analyse du fichier en cours...', 'info');
  try {
    const data = await fetchJson('/api/batch', { method: 'POST', body: form });
    lastBatchIdentifiers = (data.results || []).map((item) => item.identifier).filter(Boolean);
    hideStatus();
    renderBatch(toBatchRows(data.results || []));
  } catch (error) {
    showStatus(`<pre>${escapeHtml(error.message)}</pre>`, 'error');
  }
});

$('exportBatchBtn').addEventListener('click', () => downloadCsv(lastBatchRows));

$('exportExcelBtn').addEventListener('click', async () => {
  if (!lastBatchIdentifiers.length) return showStatus('L export Excel serveur est disponible après analyse d une liste collée.', 'error');
  const form = new FormData();
  form.append('file', new Blob([lastBatchIdentifiers.join('\n')], { type: 'text/plain' }), 'batch.txt');
  showStatus('Génération Excel en cours...', 'info');
  const response = await fetch('/api/batch/export-xlsx', { method: 'POST', body: form });
  if (!response.ok) {
    const text = await response.text();
    return showStatus(`<pre>${escapeHtml(text)}</pre>`, 'error');
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'm365_account_analyzer_export.xlsx';
  a.click();
  URL.revokeObjectURL(url);
  hideStatus();
});
