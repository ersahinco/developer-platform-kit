'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { policy, groupRefs, createPolicy } = require('./policy.cjs');
const { taskCreatePermission, taskReadPermission, actionExecutePermission } = require('@backstage/plugin-scaffolder-common/alpha');
const user = group => ({ info: { ownershipEntityRefs: groupRefs([group]) } });
test('patched resolver keeps identity stable across display-name changes and requires a subject', async () => {
  // Execute the actual compiled resolver, without starting the backend.
  const source = require('node:fs').readFileSync('packages/backend/dist/plugins/auth.cjs.js', 'utf8');
  const start = source.indexOf('async signInResolver(info, ctx) {');
  assert(start >= 0, 'Pinned resolver was not found');
  const end = source.indexOf('\n          })', start);
  assert(end > start, 'Pinned resolver boundary changed');
  const { signInResolver } = require('node:vm').runInNewContext(`({${source.slice(start, end)}})`, {
    catalogModel: require('@backstage/catalog-model'), require,
  });
  const resolve = (sub, displayName) => signInResolver({
    profile: { displayName },
    result: { fullProfile: { userinfo: { sub, groups: ['scaffold-creators'] } } },
  }, { issueToken: ({ claims }) => claims });
  for (const displayName of ['User One', 'Changed Name', undefined]) {
    const claims = await resolve('stable-id', displayName);
    assert.equal(claims.sub, 'user:default/stable-id');
    assert.equal(JSON.stringify(claims.ent), JSON.stringify([
      'user:default/stable-id', 'group:default/scaffold-creators',
    ]));
  }
  for (const sub of [undefined, '', {}, 42]) {
    await assert.rejects(resolve(sub, 'User One'), /OIDC subject is missing/);
  }
});
test('verified groups become native ownership refs; malformed or unrelated claims do not', () => {
  assert.deepEqual(groupRefs(['admin', 'scaffold-creators']), ['group:default/scaffold-creators']);
  for (const claim of [undefined, 'scaffold-creators', {}, ['/scaffold-creators']]) {
    assert.deepEqual(groupRefs(claim), []);
  }
});
test('create is allowed only for creators; unknown permissions and spoofed fields are denied', async () => {
  for (const identity of [undefined, user('scaffold-viewers'), user('admin'), { groups: ['scaffold-creators'] }]) {
    assert.equal((await policy.handle({ permission: taskCreatePermission }, identity)).result, 'DENY');
  }
  assert.equal((await policy.handle({ permission: taskCreatePermission }, user('scaffold-creators'))).result, 'ALLOW');
  assert.equal((await policy.handle({ permission: { name: 'unknown' } }, user('scaffold-creators'))).result, 'DENY');
});
test('viewers can browse templates but cannot read tasks or mutate catalog', async () => {
  for (const name of ['catalog.entity.read', 'scaffolder.template.parameter.read']) {
    assert.equal((await policy.handle({ permission: { name } }, user('scaffold-viewers'))).result, 'ALLOW');
  }
  for (const name of ['scaffolder.task.cancel', 'catalog.location.create']) {
    assert.equal((await policy.handle({ permission: { name } }, user('scaffold-viewers'))).result, 'DENY');
  }
});
test('task reads use a native empty owner filter for anyone without creator access', async () => {
  for (const identity of [undefined, user('scaffold-viewers'), user('admin')]) {
    const result = await policy.handle({ permission: taskReadPermission }, identity);
    assert.equal(result.result, 'CONDITIONAL');
    assert.equal(result.conditions.rule, 'IS_TASK_OWNER');
    assert.deepEqual(result.conditions.params, { createdBy: [] });
  }
  assert.equal((await policy.handle({ permission: taskReadPermission }, user('scaffold-creators'))).result, 'ALLOW');
});
test('creators get an action allowlist, never unrestricted action execution', async () => {
  const result = await policy.handle({ permission: actionExecutePermission }, user('scaffold-creators'));
  assert.equal(result.result, 'CONDITIONAL');
  assert.deepEqual(result.conditions.anyOf.map(c => c.params.actionId), [
    'fetch:template', 'publish:gitea', 'publish:github', 'catalog:register',
    'github:repo:create', 'github:environment:create', 'github:repo:push',
  ]);
  assert.equal((await policy.handle({ permission: actionExecutePermission }, user('scaffold-viewers'))).result, 'DENY');
});
test('client groups replace demo access and empty lists deny everyone', async () => {
  const creators = ['group:default/platform-creators'];
  const clientPolicy = createPolicy(creators, []);
  const member = { info: { ownershipEntityRefs: creators } };
  assert.equal((await clientPolicy.handle({ permission: taskCreatePermission }, member)).result, 'ALLOW');
  assert.equal((await clientPolicy.handle({ permission: taskCreatePermission }, user('scaffold-creators'))).result, 'DENY');
  assert.equal((await createPolicy([], []).handle({ permission: taskCreatePermission }, member)).result, 'DENY');
});
