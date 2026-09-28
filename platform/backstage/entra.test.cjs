'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { microsoftSignInResolvers } = require('@backstage/plugin-auth-backend-module-microsoft-provider');
const { defaultGroupTransformer, defaultUserTransformer } = require('@backstage/plugin-catalog-backend-module-msgraph');
const { stringifyEntityRef } = require('@backstage/catalog-model');
const { taskCreatePermission } = require('@backstage/plugin-scaffolder-common/alpha');
const { createPolicy } = require('./policy.cjs');
const { ConfigSources } = require('@backstage/config-loader');
const { ScmIntegrations } = require('@backstage/integration');

test('shared config uses native GitHub host and private database CA overrides', async () => {
  for (const host of ['github.com', 'github.example.com']) {
    const apiBaseUrl = host === 'github.com' ? 'https://api.github.com' : `https://${host}/api/v3`;
    const env = {
      APP_CONFIG_backend_database_connection_ssl_ca: 'test-private-ca',
      GITHUB_APP_ID: '1', GITHUB_APP_CLIENT_ID: 'offline-client',
      GITHUB_APP_CLIENT_SECRET: 'offline-secret', GITHUB_APP_PRIVATE_KEY: 'offline-key',
      GITHUB_ORGANIZATION: 'acme',
      ...(host === 'github.com' ? {} : { GITHUB_HOST: host, GITHUB_API_URL: apiBaseUrl }),
    };
    const config = await ConfigSources.toConfig(ConfigSources.default({
      argv: ['--config', 'platform/entra.yaml'], watch: false, env,
      substitutionFunc: async name => env[name],
    }));
    config.close();
    const integration = ScmIntegrations.fromConfig(config).github.byHost(host);
    assert.equal(integration.config.apiBaseUrl, apiBaseUrl);
    assert.equal(config.getString('backend.database.connection.ssl.ca'), 'test-private-ca');
    assert.equal(config.getBoolean('backend.database.connection.ssl.rejectUnauthorized'), true);
  }
});

test('native Microsoft sign-in matches directory ID, never a mutable email address', async () => {
  const resolve = microsoftSignInResolvers.userIdMatchingUserEntityAnnotation();
  const id = '01234567-1234-1234-1234-012345678901';
  const directoryUser = await defaultUserTransformer({
    id, displayName: 'Test Person', userPrincipalName: 'person@example.com',
  });
  assert.equal(directoryUser.metadata.annotations['graph.microsoft.com/user-id'], id);
  for (const email of ['person@example.com', 'renamed@example.com']) {
    const result = await resolve({
      profile: { email }, result: { fullProfile: { id } },
    }, {
      async signInWithCatalogUser(query, options) {
        assert.deepEqual(query, { annotations: { 'graph.microsoft.com/user-id': id } });
        assert.equal(options.dangerousEntityRefFallback, undefined);
        return 'catalog-identity';
      },
    });
    assert.equal(result, 'catalog-identity');
  }
  await assert.rejects(resolve({ result: { fullProfile: {} } }, {}), /no id/);
  await assert.rejects(resolve({ result: { fullProfile: { id } } }, {
    async signInWithCatalogUser() { throw new Error('User is not in the catalog'); },
  }), /not in the catalog/);
});

test('permissions use native Graph group refs; selecting an ID is not itself a permission grant', async () => {
  const id = '01234567-1234-1234-1234-012345678902';
  const group = await defaultGroupTransformer({ id, displayName: 'Platform Creators', securityEnabled: true });
  assert.equal(group.metadata.annotations['graph.microsoft.com/group-id'], id);
  const ref = stringifyEntityRef(group);
  const policy = createPolicy([ref], []);
  const decide = ownershipEntityRefs => policy.handle({ permission: taskCreatePermission }, {
    info: { ownershipEntityRefs },
  });
  assert.equal((await decide([ref])).result, 'ALLOW');
  assert.equal((await decide([`group:default/${id}`])).result, 'DENY');
  assert.equal((await decide([])).result, 'DENY');
});
