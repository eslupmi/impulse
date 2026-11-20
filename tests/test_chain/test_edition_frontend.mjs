import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

async function loadEdition(edition) {
    const source = await readFile(new URL(`../../${edition}/static/js/chain_conditions.js`, import.meta.url), 'utf8');
    return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
}

const community = await loadEdition('community');
let enterprise;
try {
    enterprise = await loadEdition('enterprise');
} catch (error) {
    if (error.code !== 'ENOENT') throw error;
}

test('community adds no condition controls or metadata', () => {
    const step = {user: 'alice'};
    const container = {
        append() { assert.fail('Community must not add a condition control'); },
        querySelector() { assert.fail('Community must not read a condition control'); },
    };
    community.mountCondition(container, step);
    assert.deepEqual(community.readStepMetadata(container), {});
    assert.equal(community.conditionText(step), '');
    assert.deepEqual(step, {user: 'alice'});
});

test('enterprise round-trips condition text without evaluating it', {skip: !enterprise}, () => {
    const expression = 'team == " core "';
    const container = {querySelector: () => ({value: `  ${expression}  `})};
    assert.deepEqual(enterprise.readStepMetadata(container), {if: expression});
    assert.equal(enterprise.conditionText({user: 'alice', if: expression}), ` (if ${expression})`);
});

test('enterprise omits blank conditions', {skip: !enterprise}, () => {
    const container = {querySelector: () => ({value: '   '})};
    assert.deepEqual(enterprise.readStepMetadata(container), {});
    assert.equal(enterprise.conditionText({user: 'alice'}), '');
});

test('enterprise returns condition markup as plain text for the shared renderer', {skip: !enterprise}, () => {
    const expression = 'team == "<img src=x onerror=alert(1)>"';
    assert.equal(enterprise.conditionText({if: expression}), ` (if ${expression})`);
});
