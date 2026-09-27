'use strict';
const { createBackendModule, coreServices } = require('@backstage/backend-plugin-api');
const { policyExtensionPoint } = require('@backstage/plugin-permission-node/alpha');
const { AuthorizeResult } = require('@backstage/plugin-permission-common');
const {
  createScaffolderActionConditionalDecision,
  scaffolderActionConditions,
  createScaffolderTaskConditionalDecision,
  scaffolderTaskConditions,
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
const actions = [
  'fetch:template', 'publish:gitea', 'publish:github', 'catalog:register',
  'github:repo:create', 'github:environment:create', 'github:repo:push',
];
function createPolicy(
  creators = ['group:default/scaffold-creators'],
  viewers = ['group:default/scaffold-viewers'],
) {
  return {
    async handle({ permission }, user) {
      const refs = user?.info?.ownershipEntityRefs ?? [];
      const creator = creators.some(group => refs.includes(group));
      const member = creator || viewers.some(group => refs.includes(group));
      if (member && readable.has(permission.name) || creator && writable.has(permission.name)) {
        return { result: AuthorizeResult.ALLOW };
      }
      if (permission.name === 'scaffolder.task.read') {
        // The pinned scaffolder 3.4.0 list path ignores a plain DENY. Its native
        // owner condition filters the list and also denies individual reads.
        return createScaffolderTaskConditionalDecision(permission,
          scaffolderTaskConditions.isTaskOwner({ createdBy: [] }));
      }
      if (creator && permission.name === 'scaffolder.action.execute') {
        return createScaffolderActionConditionalDecision(permission, {
          anyOf: actions.map(actionId => scaffolderActionConditions.hasActionId({ actionId })),
        });
      }
      return { result: AuthorizeResult.DENY };
    },
  };
}
const policy = createPolicy();
const moduleRegistration = createBackendModule({
  pluginId: 'permission',
  moduleId: 'platform-groups',
  register(reg) {
    reg.registerInit({
      deps: { policies: policyExtensionPoint, config: coreServices.rootConfig },
      async init({ policies, config }) {
        policies.setPolicy(createPolicy(
          config.getOptionalStringArray('permission.platform.creators'),
          config.getOptionalStringArray('permission.platform.viewers'),
        ));
      },
    });
  },
});
module.exports = { groupRefs, policy, createPolicy, moduleRegistration };
