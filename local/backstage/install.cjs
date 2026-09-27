'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const semver = require('semver');
const dependencies = require('@backstage/plugin-permission-backend/package.json').dependencies;
for (const [name, range] of Object.entries(dependencies)) {
  if (name.startsWith('@types/')) continue;
  let dir = path.dirname(require.resolve(name));
  while (!fs.existsSync(path.join(dir, 'package.json'))) dir = path.dirname(dir);
  const version = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'))).version;
  assert(semver.satisfies(version, range), `${name} ${version} does not satisfy ${range}`);
}
const file = 'packages/backend/dist/index.cjs.js';
let source = fs.readFileSync(file, 'utf8');
function replaceOnce(before, after) {
  assert.equal(source.split(before).length, 2, `Pinned CNOE integration changed: ${before}`);
  source = source.replace(before, after);
}
// Use the standard immutable OIDC subject without rewriting Keycloak's name claim.
replaceOnce('const { profile } = info;', 'const subject = info.result.fullProfile.userinfo.sub;');
replaceOnce('if (!profile.displayName)', 'if (typeof subject !== "string" || !subject)');
replaceOnce('Login failed, user profile does not contain a valid name', 'Login failed, OIDC subject is missing');
replaceOnce('name: info.profile.displayName,', 'name: subject,');
replaceOnce('ent: [userRef],', `ent: [userRef, ...require('/app/platform-permissions/policy.cjs').groupRefs(info.result.fullProfile.userinfo.groups)],`);
replaceOnce('backend.start();', `backend.add(import('@backstage/plugin-permission-backend/alpha'));
backend.add(require('/app/platform-permissions/policy.cjs').moduleRegistration);
backend.start();`);
fs.writeFileSync(file, source);
