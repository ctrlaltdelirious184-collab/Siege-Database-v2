const http = require('http');

// ── Internals ─────────────────────────────────────────────

let _connectedLogged = false;
let _currentAppIGN   = ''; 
let _importAllGuild  = false;

function getConfig(config) {
  return (config.Config.Plugins['SiegeDatabase']) || {};
}

function postBattle(proxy, entry, port) {
  const body = JSON.stringify(entry);
  const options = {
    hostname: '127.0.0.1', port: port, path: '/ingest', method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    timeout: 3000,
  };
  const req = http.request(options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        const resp = JSON.parse(data);
        if (resp.status === 'ok') {
          proxy.log({ type: 'success', source: 'plugin', name: 'SiegeDatabase',
            message: `⚔️ Battle logged: ${resp.offense || '?'} vs ${resp.defense || '?'} — ${resp.result || '?'}`
          });
        }
      } catch (_) {}
    });
  });
  req.on('error', () => {});
  req.write(body);
  req.end();
}

function postDiscovery(proxy, type, data, port) {
  const body = JSON.stringify({ type, data });
  const options = {
    hostname: '127.0.0.1', port: port, path: '/discovery', method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    timeout: 3000,
  };
  const req = http.request(options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      if (res.statusCode === 200) {
        try {
          const resp = JSON.parse(data);
          if (resp.status === 'ok' && resp.count > 0) {
            proxy.log({ type: 'success', source: 'plugin', name: 'SiegeDatabase',
              message: `Grabbed those defenses! ⚔️`
            });
          }
        } catch (_) {}
      }
    });
  });
  req.on('error', () => {});
  req.write(body);
  req.end();
}

function processBattleLog(proxy, data, pluginCfg) {
  proxy.log({ type: 'info', source: 'plugin', name: 'SiegeDatabase',
    message: `📋 Battle log received — scanning for battles...`
  });

  const wizardName = (_currentAppIGN || pluginCfg.wizardName || '').trim().toLowerCase();
  const port       = parseInt(pluginCfg.serverPort, 10) || 7831;
  const logList    = data.log_list || [];
  const directLogs = data.battle_log_list || [];
  let allMatches = [...logList];

  // If it's a flat list (ByWizardId personal log), wrap it so the loop works
  if (directLogs.length > 0) {
    allMatches.push({ battle_log_list: directLogs, match_id: data.match_id || 0 });
  }

  let sentCount = 0;
  let skipCount = 0;

  for (const match of allMatches) {
    const battles = match.battle_log_list || [];
    for (const entry of battles) {
      const entryWiz = (entry.wizard_name || '').trim().toLowerCase();

      if (wizardName && !_importAllGuild) {
        if (entryWiz && entryWiz !== wizardName) {
          skipCount++;
          continue;
        }
      }
      postBattle(proxy, entry, port);
      sentCount++;
    }
  }

  proxy.log({ type: 'error', source: 'plugin', name: 'SiegeDatabase',
    message: `📊 SUMMARY: Sent ${sentCount} | Skipped ${skipCount} battles. (Filter: "${wizardName || 'NONE'}")`
  });

  if (skipCount > 0 && !_importAllGuild) {
    proxy.log({ type: 'warning', source: 'plugin', name: 'SiegeDatabase',
      message: `⚠ Note: The skipped battles were for a different IGN than "${wizardName}".`
    });
  }
}

// ── Plugin export ─────────────────────────────────────────

module.exports = {
  defaultConfig: { enabled: true, wizardName: '', serverPort: 7831, debug: false },
  defaultConfigDetails: {
    wizardName: { label: 'Your In-Game Name (IGN)', type: 'text' },
    serverPort: { label: 'Siege Database Server Port', type: 'number' },
    debug:      { label: 'Debug Mode (Logs all commands)', type: 'checkbox' }
  },
  pluginName:        'SiegeDatabase',
  pluginDescription: 'Real-time siege battle ingestion and defense discovery.',

  init(proxy, config) {
    const TARGET_CMDS = [
      'GetGuildSiegeBattleLog',
      'GetGuildSiegeBattleLogByWizardId',
      'GetGuildSiegeDefenseDeckByWizardId',
      'GetGuildSiegeBaseInfo',
      'GetGuildSiegeRankingInfo',
      'GetGuildSiegeBaseDefenseUnitListPreset'
    ];

    // ── Robust Command Listener
    proxy.on('apiCommand', (name, data) => {
      const cfg = getConfig(config);
      if (!cfg.enabled) return;
      const port = parseInt(cfg.serverPort, 10) || 7831;

      if (TARGET_CMDS.includes(name)) {
        proxy.log({ type: 'info', source: 'plugin', name: 'SiegeDatabase',
          message: `🔔 Detected: ${name}`
        });

        if (name.includes('BattleLog')) {
          processBattleLog(proxy, data, cfg);
        } else {
          postDiscovery(proxy, name, data, port);
        }
      }
    });

    // ── Heartbeat Loop (10s)
    setInterval(() => {
      const cfg = getConfig(config);
      if (!cfg.enabled) return;
      const port = parseInt(cfg.serverPort, 10) || 7831;
      const req = http.request({ hostname: '127.0.0.1', port: port, path: '/health', method: 'GET', timeout: 2000 }, (res) => { 
        let raw = '';
        res.on('data', (c) => { raw += c; });
        res.on('end', () => {
          try {
            const body = JSON.parse(raw);
            if (body.status === 'running') {
              _currentAppIGN = body.wizard_name || ''; 
              _importAllGuild = body.import_all_guild === true;
              if (!_connectedLogged) {
                proxy.log({ type: 'success', source: 'plugin', name: 'SiegeDatabase',
                  message: `[v2.1] Connected to SiegeDB (Tracking: ${_currentAppIGN || 'Any'})`
                });
                _connectedLogged = true;
              }
            }
          } catch (_) {}
        });
      });
      req.on('error', () => { _connectedLogged = false; });
      req.end();
    }, 10000);
  },
};
