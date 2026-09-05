import assert from 'node:assert/strict'

import { computeCurrentWeek } from '../../src/utils/semesterWeek.js'

// Monday-start weeks
assert.equal(computeCurrentWeek('2026-08-31', '2026-08-31'), 1)
assert.equal(computeCurrentWeek('2026-08-31', '2026-09-04'), 1)
assert.equal(computeCurrentWeek('2026-08-31', '2026-09-06'), 1)
assert.equal(computeCurrentWeek('2026-08-31', '2026-09-07'), 2)
assert.equal(computeCurrentWeek('2026-08-31', '2026-12-06'), 14)
assert.equal(computeCurrentWeek('2026-08-31', '2026-12-07'), 15)

// Mid-week start still counts that partial week as week 1
assert.equal(computeCurrentWeek('2026-09-02', '2026-09-05'), 1)

// Before the semester or after 30 weeks there is no current week
assert.equal(computeCurrentWeek('2026-09-07', '2026-09-05'), null)
assert.equal(computeCurrentWeek('2026-08-31', '2027-04-05'), null)

// Week 30 spans start + 203..209 days (2027-03-22..2027-03-28)
assert.equal(computeCurrentWeek('2026-08-31', '2027-03-22'), 30)
assert.equal(computeCurrentWeek('2026-08-31', '2027-03-28'), 30)
assert.equal(computeCurrentWeek('2026-08-31', '2027-03-29'), null)

// Invalid inputs degrade to null instead of throwing
assert.equal(computeCurrentWeek('', new Date()), null)
assert.equal(computeCurrentWeek('2026/08/31', new Date()), null)
assert.equal(computeCurrentWeek(undefined, '2026-09-05'), null)
assert.equal(computeCurrentWeek('2026-08-31', 'not-a-date'), null)

// Date objects are accepted for the current day
assert.equal(computeCurrentWeek('2026-08-31', new Date(2026, 8, 4)), 1)

console.log('semester week contract check passed')
