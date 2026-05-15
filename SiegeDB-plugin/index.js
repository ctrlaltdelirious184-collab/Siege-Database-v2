const http = require('http');

// ── Internals ─────────────────────────────────────────────

let _connectedLogged = false;
let _currentAppIGN = '';
let _importAllGuild = false;

function getConfig(config) {
  return (config.Config.Plugins['SiegeDatabase']) || {};
}

function postBattle(proxy, entry, port, verbose) {
  return new Promise((resolve) => {
    const body = JSON.stringify(entry);
    const options = {
      hostname: '127.0.0.1', port: port, path: '/ingest', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      timeout: 5000,
    };
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const resp = JSON.parse(data);
          if (resp.status === 'ok') {
            if (verbose) {
              proxy.log({
                type: 'success', source: 'plugin', name: 'SiegeDatabase',
                message: `⚔️ Logged: ${resp.offense || '?'} vs ${resp.defense || '?'}`
              });
            }
            resolve(true);
          } else {
            resolve(false);
          }
        } catch (_) { resolve(false); }
      });
    });
    req.on('error', () => { resolve(false); });
    req.write(body);
    req.end();
  });
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
            proxy.log({
              type: 'success', source: 'plugin', name: 'SiegeDatabase',
              message: `Grabbed those defenses! ⚔️`
            });
          }
        } catch (_) { }
      }
    });
  });
  req.on('error', () => { });
  req.write(body);
  req.end();
}

async function processBattleLog(proxy, data, pluginCfg) {
  const verbose = pluginCfg.verboseLogs !== false;
  if (verbose) {
    proxy.log({ type: 'info', source: 'plugin', name: 'SiegeDatabase', message: `🔍 Scanning battle history...` });
  }

  const wizardName = (_currentAppIGN || pluginCfg.wizardName || '').trim().toLowerCase();
  const port = parseInt(pluginCfg.serverPort, 10) || 7831;
  const logList = data.log_list || [];
  const directLogs = data.battle_log_list || [];
  let allMatches = [...logList];

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

      // Sequential Wait
      const res = await postBattle(proxy, entry, port, verbose);
      if (res) sentCount++;
    }
  }

  if (verbose && sentCount > 0) {
    proxy.log({
      type: 'success', source: 'plugin', name: 'SiegeDatabase',
      message: `📊 [v2.8] SUMMARY: Ingested ${sentCount} battle(s).`
    });
  }
}

// ── Plugin export ─────────────────────────────────────────

module.exports = {
  defaultConfig: { enabled: true, wizardName: '', serverPort: 7831, verboseLogs: true },
  defaultConfigDetails: {
    wizardName: { label: 'Your In-Game Name (IGN)', type: 'text' },
    serverPort: { label: 'Siege Database Server Port', type: 'number' },
    verboseLogs: { label: 'Show Detailed Logs in SWEX', type: 'checkbox' }
  },
  pluginName: 'SiegeDatabase',
  pluginDescription: 'Real-time siege battle ingestion and defense discovery.',

  setup(proxy, config) {
    const CMD_MAP = {
      'GetGuildSiegeBattleLog': 'Siege Battle History',
      'GetGuildSiegeBattleLogByWizardId': 'Personal Battle History',
      'GetGuildSiegeDefenseDeckByWizardId': 'Defense Loadout',
      'GetGuildSiegeBaseInfo': 'Siege Map Info',
      'GetGuildSiegeRankingInfo': 'Siege Rankings',
      'GetGuildSiegeBaseDefenseUnitListPreset': 'Defense Presets'
    };

    // ── Explicit Listeners
    Object.keys(CMD_MAP).forEach(cmd => {
      proxy.on(cmd, (req, resp) => {
        const cfg = getConfig(config);
        if (!cfg.enabled) return;

        if (cfg.verboseLogs !== false) {
          proxy.log({ type: 'info', source: 'plugin', name: 'SiegeDatabase', message: `✨ Syncing: ${CMD_MAP[cmd]}` });
        }

        if (cmd.includes('BattleLog')) {
          processBattleLog(proxy, resp, cfg);
        } else {
          postDiscovery(proxy, cmd, resp, 7831);
        }
      });
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
                proxy.log({
                  type: 'success', source: 'plugin', name: 'SiegeDatabase',
                  message: `[v2.8] Monitoring Siege (Tracking: ${_currentAppIGN || 'Any'})`
                });
                _connectedLogged = true;
              }
            }
          } catch (_) { }
        });
      });
      req.on('error', () => { _connectedLogged = false; });
      req.end();
    }, 10000);
  },
  init(proxy, config) {
    this.setup(proxy, config);
  }
};
