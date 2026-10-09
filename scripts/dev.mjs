// npm run dev - start EM6 Brain locally (no Docker) in ONE terminal.
// Reads .env, prepares packages, starts every service with a coloured label.
// Ctrl+C stops everything. Ollama runs separately.

import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const win = process.platform === 'win32';
const say = (msg) => console.log(`\x1b[36m[dev]\x1b[0m ${msg}`);

// ---- 1. Settings: .env, then the local addresses --------------------------
const envPath = join(root, '.env');
if (!existsSync(envPath)) {
  say('.env not found. Copy .env.example to .env and set POSTGRES_PASSWORD.');
  process.exit(1);
}
const fromFile = {};
for (const line of readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const l = line.trim();
  if (!l || l.startsWith('#') || !l.includes('=')) continue;
  const i = l.indexOf('=');
  fromFile[l.slice(0, i).trim()] = l.slice(i + 1).trim();
}
const env = { ...process.env, ...fromFile, PYTHONUNBUFFERED: '1', NG_CLI_ANALYTICS: 'false' };
if (!env.BRAIN_URL || env.BRAIN_URL.includes('host.docker.internal')) {
  env.BRAIN_URL = 'http://127.0.0.1:11434';   // Ollama listens on IPv4 only
}
env.TOOL_SERVICES = 'http://127.0.0.1:8101,http://127.0.0.1:8102';
env.FILES_DIR = join(root, 'data', 'uploads');  // attached files stay on this PC
delete env.DATABASE_URL;                         // built from POSTGRES_PASSWORD by the app
mkdirSync(env.FILES_DIR, { recursive: true });

// ---- 2. Packages ------------------------------------------------------------
function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: win, env, ...opts });
  if (r.status !== 0) {
    say(`Failed: ${cmd} ${args.join(' ')}`);
    process.exit(1);
  }
}
const py = join(root, '.venv', win ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(py)) {
  say('Creating Python environment (first run only)...');
  run(win ? 'python' : 'python3', ['-m', 'venv', join(root, '.venv')]);
}
say('Checking Python packages...');
run(py, ['-m', 'pip', 'install', '--quiet', '--disable-pip-version-check',
  '-r', join(root, 'orchestrator', 'requirements.txt'),
  '-r', join(root, 'tools', 'clock-tool', 'requirements.txt'),
  '-r', join(root, 'tools', 'excel-tool', 'requirements.txt')], { shell: false });
if (!existsSync(join(root, 'frontend', 'node_modules'))) {
  say('Installing front-end packages (first run only, a few minutes)...');
  run('npm', ['install'], { cwd: join(root, 'frontend') });
}

// ---- 3. Is the brain up? (warning only) ---------------------------------------
try {
  const r = await fetch(`${env.BRAIN_URL}/api/tags`, { signal: AbortSignal.timeout(3000) });
  const names = (await r.json()).models?.map((m) => m.name) ?? [];
  const model = env.BRAIN_MODEL || 'qwen2.5:7b';
  say(names.includes(model) ? `Brain OK (${model}).`
    : `\x1b[33mOllama is up but '${model}' isn't listed - check OLLAMA_MODELS.\x1b[0m`);
} catch {
  say(`\x1b[33mOllama isn't answering at ${env.BRAIN_URL}. Start it; the app will pick it up.\x1b[0m`);
}

// ---- 4. Start the services ----------------------------------------------------
const uvicorn = (port) => [py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)]];
const services = [
  { name: 'clock    ', color: 35, cwd: 'tools/clock-tool', cmd: uvicorn(8101) },
  { name: 'excel    ', color: 33, cwd: 'tools/excel-tool', cmd: uvicorn(8102) },
  { name: 'orchestr ', color: 32, cwd: 'orchestrator', cmd: uvicorn(8000) },
  { name: 'frontend ', color: 34, cwd: 'frontend', cmd: ['npm', ['start']], shell: win },
];

const children = [];
let stopping = false;
for (const s of services) {
  const [cmd, args] = s.cmd;
  const child = spawn(cmd, args, { cwd: join(root, s.cwd), env, shell: !!s.shell });
  const label = `\x1b[${s.color}m${s.name}|\x1b[0m `;
  const pipe = (stream) => {
    let buf = '';
    stream.on('data', (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const line of lines) if (line.trim()) console.log(label + line);
    });
  };
  pipe(child.stdout);
  pipe(child.stderr);
  child.on('exit', (code) => {
    if (!stopping) console.log(`${label}\x1b[31mstopped (exit ${code}). The others keep running.\x1b[0m`);
  });
  children.push(child);
}
say('Starting... open http://localhost:4200 in ~20 s.  API docs: http://localhost:8000/docs.  Ctrl+C stops all.');

// ---- 5. Ctrl+C stops everything ------------------------------------------------
function stopAll() {
  if (stopping) return;
  stopping = true;
  say('Stopping...');
  for (const c of children) {
    if (c.exitCode !== null) continue;
    if (win) spawnSync('taskkill', ['/pid', String(c.pid), '/T', '/F'], { stdio: 'ignore' });
    else c.kill('SIGTERM');
  }
  setTimeout(() => process.exit(0), 500);
}
process.on('SIGINT', stopAll);
process.on('SIGTERM', stopAll);
