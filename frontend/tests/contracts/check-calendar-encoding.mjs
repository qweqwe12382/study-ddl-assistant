import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Campus portals still export GBK calendars; the upload flow must recover
// from Blob.text()'s UTF-8 replacement instead of importing mojibake names.
const GBK_SUMMARY = Buffer.from([0xB8, 0xDF, 0xB5, 0xC8, 0xCA, 0xFD, 0xD1, 0xA7]) // "高等数学"
const gbkDecoded = new TextDecoder('gbk').decode(GBK_SUMMARY)
assert.equal(gbkDecoded, '高等数学')

// The retry trigger: the same bytes decoded as UTF-8 must yield U+FFFD.
const utf8Decoded = new TextDecoder('utf-8').decode(GBK_SUMMARY)
assert.ok(utf8Decoded.includes('\uFFFD'))

const source = readFileSync(fileURLToPath(new URL('../../src/components/AcademicIntegrationDialog.vue', import.meta.url)), 'utf8')
const upload = source.match(/async function readCalendarFile\(event\) \{[\s\S]*?\nasync function /)?.[0]
assert.ok(upload, 'readCalendarFile must remain before the next async function in AcademicCalendarDialog.vue')
assert.match(upload, /includes\('\\uFFFD'\)/)
assert.match(upload, /new TextDecoder\('gbk'\)/)
// A GBK retry that still fails must keep the UTF-8 text, never a mojibake mix.
assert.match(upload, /if \(!decoded\.includes\('\\uFFFD'\)\) calendarText\.value = decoded/)

console.log('Calendar encoding fallback passed: GBK uploads decode without mojibake.')
