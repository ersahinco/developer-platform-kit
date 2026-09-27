'use strict';
// Boot the actual shared configuration offline with temporary storage. This
// checks composition and the OAuth redirect, not a real Entra login or consent.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { mkdtempSync, writeFileSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { generateKeyPairSync } = require('node:crypto');

test('shared image boots without Kubernetes and exposes native Microsoft sign-in', { timeout: 90000 }, async t => {
  const directory = mkdtempSync(join(tmpdir(), 'platform-runtime-'));
  const config = join(directory, 'config.json');
  writeFileSync(config, JSON.stringify({
    backend: { database: { client: 'better-sqlite3', connection: ':memory:', pluginDivisionMode: 'database' } },
    catalog: {
      locations: [],
      providers: { microsoftGraphOrg: { client: { schedule: { initialDelay: { hours: 1 } } } } },
    },
  }));
  const { privateKey } = generateKeyPairSync('rsa', {
    modulusLength: 2048,
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    publicKeyEncoding: { type: 'spki', format: 'pem' },
  });
  const baseUrl = 'http://localhost:7007';
  const tenant = '01234567-1234-1234-1234-012345678901';
  const child = spawn(process.execPath, ['packages/backend', '--config', 'platform/entra.yaml', '--config', config], {
    env: {
      ...process.env,
      PORTAL_URL: baseUrl,
      POSTGRES_HOST: 'unused', POSTGRES_PORT: '5432', POSTGRES_DATABASE: 'unused',
      POSTGRES_USER: 'unused', POSTGRES_PASSWORD: 'unused',
      SESSION_SECRET: 'offline-runtime-test-session-secret',
      ENTRA_TENANT_ID: tenant, ENTRA_CLIENT_ID: tenant, ENTRA_CLIENT_SECRET: 'offline-test',
      ENTRA_CREATORS_GROUP_ID: tenant, ENTRA_VIEWERS_GROUP_ID: tenant,
      ENTRA_CREATORS_GROUP_REF: 'group:default/creators', ENTRA_VIEWERS_GROUP_REF: 'group:default/viewers',
      GITHUB_APP_ID: '1', GITHUB_APP_PRIVATE_KEY: privateKey, GITHUB_ORGANIZATION: 'acme',
      GITHUB_APP_CLIENT_ID: 'offline-client', GITHUB_APP_CLIENT_SECRET: 'offline-secret',
      TEMPLATES_CATALOG_URL: 'https://github.com/acme/templates/blob/main/catalog-info.yaml',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let logs = '';
  child.stdout.on('data', chunk => { logs += chunk; });
  child.stderr.on('data', chunk => { logs += chunk; });
  t.after(async () => {
    if (child.exitCode === null) {
      const exited = once(child, 'exit');
      child.kill('SIGTERM');
      await exited;
    }
    rmSync(directory, { recursive: true, force: true });
  });
  let ready = false;
  for (let attempt = 0; attempt < 120; attempt++) {
    assert.equal(child.exitCode, null, `Backend exited during startup:\n${logs}`);
    assert(!logs.includes('Backend startup failed'), `Backend startup failed:\n${logs}`);
    ready = await fetch(`${baseUrl}/.backstage/health/v1/readiness`).then(r => r.ok).catch(() => false);
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  assert(ready, `Backend did not become ready:\n${logs}`);
  const html = await fetch(baseUrl).then(r => r.text());
  assert.match(html, /signInProvider.{1,20}microsoft/, 'Frontend must receive the selected identity provider');
  const signIn = await fetch(`${baseUrl}/api/auth/microsoft/start?env=production&origin=${encodeURIComponent(baseUrl)}&scope=user.read`, { redirect: 'manual' });
  assert.equal(signIn.status, 302, await signIn.text());
  const redirect = new URL(signIn.headers.get('location'));
  assert.equal(redirect.hostname, 'login.microsoftonline.com');
  assert(redirect.pathname.includes(tenant));
  assert.equal(redirect.searchParams.get('redirect_uri'), `${baseUrl}/api/auth/microsoft/handler/frame`);
  assert.equal((await fetch(`${baseUrl}/api/catalog/entities`)).status, 401);
  assert.equal((await fetch(`${baseUrl}/api/terraform/getTFStateFile`, { method: 'POST' })).status, 404);
});
