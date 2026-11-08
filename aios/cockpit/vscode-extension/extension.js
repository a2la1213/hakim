/* Extension VSCode — ouvre le Cockpit dans un panneau webview (iframe vers le serveur local).
   Démarre le serveur si besoin (start.sh, sans ouvrir de navigateur). */
const vscode = require('vscode');
const { exec } = require('child_process');

const PORT = process.env.COCKPIT_PORT || 4317;
const URL = `http://localhost:${PORT}`;
const START = '/Users/admin/AIOS/cockpit/start.sh';

function activate(context) {
  const cmd = vscode.commands.registerCommand('cockpit.open', () => {
    // démarrage idempotent du serveur (sans ouvrir le navigateur)
    exec(`COCKPIT_OPEN_BROWSER=0 bash ${START}`, () => {});

    const panel = vscode.window.createWebviewPanel(
      'aiosCockpit', '◆ Claude Cockpit', vscode.ViewColumn.Active,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    panel.webview.html = `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; frame-src ${URL}; style-src 'unsafe-inline';">
<style>html,body{margin:0;padding:0;height:100vh;width:100%;overflow:hidden;background:#070a16}
iframe{border:0;width:100%;height:100vh}</style></head>
<body><iframe src="${URL}"></iframe></body></html>`;
  });
  context.subscriptions.push(cmd);
}
function deactivate() {}
module.exports = { activate, deactivate };
