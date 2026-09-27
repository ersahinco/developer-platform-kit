'use strict';
// Run the pinned native actions against an offline GitHub API double. The input
// comes from our real exporter, so package/schema drift breaks portal-check.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const { once } = require('node:events');
const { ConfigReader } = require('@backstage/config');
const { ScmIntegrations } = require('@backstage/integration');
const { validate } = require('jsonschema');
const sodium = require('libsodium-wrappers');
const github = require('@backstage/plugin-scaffolder-backend-module-github');

for (const name of ['app', 'infra', 'data']) {
  test(`${name}: native actions configure team, delivery and environments`, async t => {
    await sodium.ready;
    const key = sodium.crypto_box_keypair();
    const requests = [];
    const decrypted = {};
    const warnings = [];
    const server = http.createServer(async (req, res) => {
      let raw = '';
      for await (const chunk of req) raw += chunk;
      const body = raw ? JSON.parse(raw) : {};
      const route = `${req.method} ${req.url}`;
      requests.push({ route, body });
      let response = {};
      if (route === 'GET /users/acme') response = { type: 'Organization' };
      else if (route === 'POST /orgs/acme/repos') {
        response = { id: 1, clone_url: `https://github.com/acme/${name}.git` };
      } else if (route === `GET /repos/acme/${name}`) response = { id: 1 };
      else if (route === `GET /repos/acme/${name}/actions/secrets/public-key`) {
        response = { key_id: 'offline-test', key: sodium.to_base64(key.publicKey, sodium.base64_variants.ORIGINAL) };
      } else if (route.startsWith(`PUT /repos/acme/${name}/actions/secrets/`)) {
        decrypted[req.url.split('/').pop()] = sodium.crypto_box_seal_open(
          sodium.from_base64(body.encrypted_value, sodium.base64_variants.ORIGINAL),
          key.publicKey, key.privateKey, 'text',
        );
      } else if (
        !route.startsWith('PUT /orgs/acme/teams/') &&
        route !== `POST /repos/acme/${name}/actions/variables` &&
        !route.startsWith(`PUT /repos/acme/${name}/environments/`) &&
        !route.match(new RegExp(`^POST /repos/acme/${name}/environments/[^/]+/deployment-branch-policies$`))
      ) {
        res.statusCode = 404;
        response = { message: `Unexpected offline request: ${route}` };
      }
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(response));
    });
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    t.after(() => new Promise(resolve => server.close(resolve)));
    const config = new ConfigReader({ integrations: { github: [{
      host: 'github.com', apiBaseUrl: `http://127.0.0.1:${server.address().port}`,
      token: 'offline-test-token',
    }] } });
    const integrations = ScmIntegrations.fromConfig(config);
    const actions = [
      github.createGithubRepoCreateAction({ config, integrations }),
      github.createGithubEnvironmentAction({ integrations }),
      github.createGithubRepoPushAction({ config, integrations }),
    ];
    const document = JSON.parse(fs.readFileSync(`/templates/${name}/template.yaml`, 'utf8'));
    const steps = document.spec.steps.filter(step => step.action.startsWith('github:'));
    for (const step of steps) {
      const action = actions.find(candidate => candidate.id === step.action);
      assert(action, `Native action missing: ${step.action}`);
      const input = { ...step.input, repoUrl: `github.com?owner=acme&repo=${name}` };
      assert.deepEqual(validate(input, action.schema.input).errors, []);
      // A real push requires a Git server; schema-check it here. Publication is
      // covered separately by the live smoke test, never by this offline test.
      if (action.id === 'github:repo:push') continue;
      await action.handler({
        input, output() {},
        checkpoint: ({ fn }) => fn(),
        logger: { info() {}, debug() {}, warn(message) { warnings.push(message); } },
      });
    }
    assert.deepEqual(warnings, [], 'Native team assignment must not silently fail');
    const creation = steps[0].input;
    assert.deepEqual(decrypted, creation.secrets);
    const team = creation.collaborators[0];
    assert(requests.some(({ route, body }) =>
      route === `PUT /orgs/acme/teams/${team.team}/repos/acme/${name}` && body.permission === team.access));
    for (const [variable, value] of Object.entries(creation.repoVariables ?? {})) {
      assert(requests.some(({ route, body }) => route.endsWith('/actions/variables') && body.name === variable && body.value === value));
    }
    assert(requests.some(({ route, body }) => route.endsWith('/environments/aws/deployment-branch-policies') && body.name === 'main' && body.type === 'branch'));
    if (name === 'infra') {
      assert(requests.some(({ route, body }) => route.endsWith('/environments/aws-plan') && body.deployment_branch_policy == null));
    }
  });
}
