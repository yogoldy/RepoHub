const assert=require('node:assert/strict');const {label}=require('../web/readiness.js');assert.equal(label({state:'accessible'}),'Access checked');assert.equal(label({state:'blocked'}),'Access blocked');assert.equal(label({state:'injected private prose'}),'Not checked');console.log('Readiness label checks passed');

const {notificationLabel}=require('../web/readiness.js');
assert.equal(notificationLabel({permission:'waiting'}),'not requested');
assert.equal(notificationLabel({permission:'waiting',request:'pending'}),'waiting for macOS permission');
assert.match(notificationLabel({permission:'waiting',request:'failed'}),/request failed/);
assert.match(notificationLabel({permission:'waiting',request:'completed'}),/not confirmed/);
assert.equal(notificationLabel({permission:'allowed',request:'failed'}),'allowed');
assert.match(notificationLabel({permission:'denied',request:'completed'}),/denied/);
assert.equal(notificationLabel({permission:'private',request:'private'}),'not checked');
console.log('Notification request-state checks passed');
