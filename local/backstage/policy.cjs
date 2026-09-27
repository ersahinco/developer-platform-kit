'use strict';
const { createBackendModule } = require('@backstage/backend-plugin-api');
const { policyExtensionPoint } = require('@backstage/plugin-permission-node/alpha');
const { AuthorizeResult } = require('@backstage/plugin-permission-common');
const {
  createScaffolderActionConditionalDecision,
  scaffolderActionConditions,
} = require('@backstage/plugin-scaffolder-backend/alpha');

const groups = ['scaffold-creators', 'scaffold-viewers'];
// Called only with groups from the authenticated OIDC userinfo response.
function groupRefs(claim) {
  return Array.isArray(claim)
    ? groups.filter(group => claim.includes(group)).map(group => `group:default/${group}`)
    : [];
}
const readable = new Set([
  'catalog.entity.read', 'catalog.location.read',
  'scaffolder.template.parameter.read', 'scaffolder.template.step.read',
]);
const writable = new Set([
  'scaffolder.task.create', 'scaffolder.task.read', 'scaffolder.task.cancel',
  'catalog.entity.create', 'catalog.location.create', 'catalog.entity.refresh',
]);
const actions = ['fetch:template', 'publish:gitea', 'publish:github', 'catalog:register'];
const policy = {
  async handle({ permission }, user) {
    const refs = user?.info?.ownershipEntityRefs ?? [];
    const creator = refs.includes('group:default/scaffold-creators');
    const member = creator || refs.includes('group:default/scaffold-viewers');
    if (member && readable.has(permission.name) || creator && writable.has(permission.name)) {
      return { result: AuthorizeResult.ALLOW };
    }
    if (creator && permission.name === 'scaffolder.action.execute') {
      return createScaffolderActionConditionalDecision(permission, {
        anyOf: actions.map(actionId => scaffolderActionConditions.hasActionId({ actionId })),
      });
    }
    return { result: AuthorizeResult.DENY };
  },
};
const moduleRegistration = createBackendModule({
  pluginId: 'permission',
  moduleId: 'platform-groups',
  register(reg) {
    reg.registerInit({
      deps: { policies: policyExtensionPoint },
      async init({ policies }) { policies.setPolicy(policy); },
    });
  },
});
module.exports = { groupRefs, policy, moduleRegistration };
