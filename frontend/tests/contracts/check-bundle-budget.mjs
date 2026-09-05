import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const assetsDirectory = path.join(frontendDirectory, 'dist', 'assets');

// These limits leave room for normal build variance while catching a clear
// regression, such as bringing the full Element Plus stylesheet back in.
const checks = [
  {
    key: 'globalCss',
    label: 'global entry CSS',
    pattern: /^index(?:-[^/]+)?\.css$/,
    budget: 34 * 1024,
  },
  {
    key: 'dashboardJs',
    label: 'Dashboard JS',
    pattern: /^DashboardView(?:-[^/]+)?\.js$/,
    budget: 42 * 1024,
  },
  {
    key: 'dashboardCss',
    label: 'Dashboard CSS',
    pattern: /^DashboardView(?:-[^/]+)?\.css$/,
    // M8.23 adds two compact, scoped dashboard modules (Deadline Flow and AI Inbox).
    // Keep a narrow ceiling that still catches accidental full-library CSS regressions.
    budget: 10 * 1024,
  },
  {
    key: 'tasksJs',
    label: 'Tasks JS',
    pattern: /^TasksView(?:-[^/]+)?\.js$/,
    // M8.24 keeps the DDL agenda route-local; this ceiling protects lazy loading.
    budget: 18 * 1024,
  },
  {
    key: 'tasksCss',
    label: 'Tasks CSS',
    pattern: /^TasksView(?:-[^/]+)?\.css$/,
    budget: 5 * 1024,
  },
  {
    key: 'quickAddJs',
    label: 'Quick Add JS',
    pattern: /^QuickTaskAdd(?:-[^/]+)?\.js$/,
    // The concise-view quick add bar loads as its own tiny chunk.
    budget: 6 * 1024,
  },
  {
    key: 'quickAddCss',
    label: 'Quick Add CSS',
    pattern: /^QuickTaskAdd(?:-[^/]+)?\.css$/,
    budget: 2 * 1024,
  },
  {
    key: 'focusJs',
    label: 'Focus JS',
    pattern: /^FocusView(?:-[^/]+)?\.js$/,
    // The focus timer stays a small, self-contained lazy route.
    budget: 10 * 1024,
  },
  {
    key: 'focusCss',
    label: 'Focus CSS',
    pattern: /^FocusView(?:-[^/]+)?\.css$/,
    budget: 4 * 1024,
  },
  {
    key: 'materialsJs',
    label: 'Materials JS',
    pattern: /^MaterialsView(?:-[^/]+)?\.js$/,
    // M8.25 keeps the AI Inbox and confirmation recovery flow route-local.
    budget: 24 * 1024,
  },
  {
    key: 'materialsCss',
    label: 'Materials CSS',
    pattern: /^MaterialsView(?:-[^/]+)?\.css$/,
    budget: 5 * 1024,
  },
  {
    key: 'studyPlansJs',
    label: 'StudyPlans JS',
    pattern: /^StudyPlansView(?:-[^/]+)?\.js$/,
    // M8.26 keeps the weekly action board inside the lazy study-plan route.
    budget: 16 * 1024,
  },
  {
    key: 'studyPlansCss',
    label: 'StudyPlans CSS',
    pattern: /^StudyPlansView(?:-[^/]+)?\.css$/,
    budget: 6 * 1024,
  },
  {
    key: 'academicCalendarJs',
    label: 'Academic Calendar JS',
    pattern: /^AcademicCalendarView(?:-[^/]+)?\.js$/,
    // Keep the timetable, exam CRUD, and responsive day view route-local.
    budget: 8 * 1024,
  },
  {
    key: 'academicCalendarCss',
    label: 'Academic Calendar CSS',
    pattern: /^AcademicCalendarView(?:-[^/]+)?\.css$/,
    budget: 4 * 1024,
  },
  {
    key: 'academicIntegrationJs',
    label: 'Academic Integration JS',
    pattern: /^AcademicIntegrationDialog(?:-[^/]+)?\.js$/,
    // The integration shell loads only after the student opens it; the
    // credential-bearing NJUST form is split into a second short-lived chunk.
    budget: 5 * 1024,
  },
  {
    key: 'academicIntegrationCss',
    label: 'Academic Integration CSS',
    pattern: /^AcademicIntegrationDialog(?:-[^/]+)?\.css$/,
    budget: 2 * 1024,
  },
];

const largestJsBudget = 136 * 1024;

function formatBytes(bytes) {
  return `${(bytes / 1024).toFixed(2)} KiB`;
}

function readAssets() {
  if (!fs.existsSync(assetsDirectory) || !fs.statSync(assetsDirectory).isDirectory()) {
    throw new Error(`build assets directory not found: ${assetsDirectory}`);
  }

  return fs
    .readdirSync(assetsDirectory, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => ({
      name: entry.name,
      path: path.join(assetsDirectory, entry.name),
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

function measure(asset) {
  const rawBytes = fs.readFileSync(asset.path);
  return {
    ...asset,
    rawBytes: rawBytes.byteLength,
    gzipBytes: gzipSync(rawBytes).byteLength,
  };
}

function describePattern(pattern) {
  return pattern.toString();
}

let assets;
try {
  assets = readAssets();
} catch (error) {
  console.error(`Bundle budget check failed: ${error.message}`);
  process.exitCode = 1;
}

if (!assets) {
  process.exit();
}

const failures = [];
const measurements = new Map();

for (const check of checks) {
  const matches = assets.filter((asset) => check.pattern.test(asset.name));

  if (matches.length === 0) {
    failures.push(`${check.label} is missing (expected one file matching ${describePattern(check.pattern)})`);
    continue;
  }

  if (matches.length > 1) {
    failures.push(
      `${check.label} is ambiguous (expected one file matching ${describePattern(check.pattern)}, found ${matches
        .map((asset) => asset.name)
        .join(', ')})`,
    );
    continue;
  }

  measurements.set(check.key, measure(matches[0]));
}

const jsAssets = assets.filter((asset) => asset.name.endsWith('.js')).map(measure);
if (jsAssets.length === 0) {
  failures.push('largest single JS is unavailable (no .js files found in dist/assets)');
} else {
  const largestJs = jsAssets.reduce((largest, asset) => {
    if (!largest || asset.gzipBytes > largest.gzipBytes) {
      return asset;
    }
    return largest;
  }, null);
  measurements.set('largestJs', largestJs);
}

console.log('Bundle budget check (gzip, dist/assets)');
console.log('----------------------------------------');

for (const check of checks) {
  const asset = measurements.get(check.key);
  if (!asset) {
    console.log(`[FAIL] ${check.label}: missing or ambiguous required match`);
    continue;
  }

  const status = asset.gzipBytes <= check.budget ? 'PASS' : 'FAIL';
  console.log(
    `[${status}] ${check.label}: ${asset.name} — ${formatBytes(asset.gzipBytes)} gzip / ${formatBytes(
      check.budget,
    )} budget`,
  );
  if (asset.gzipBytes > check.budget) {
    failures.push(
      `${check.label} exceeds its gzip budget (${formatBytes(asset.gzipBytes)} > ${formatBytes(check.budget)})`,
    );
  }
}

const largestJs = measurements.get('largestJs');
if (!largestJs) {
  console.log('[FAIL] largest single JS: unavailable');
} else {
  const status = largestJs.gzipBytes <= largestJsBudget ? 'PASS' : 'FAIL';
  console.log(
    `[${status}] largest single JS: ${largestJs.name} — ${formatBytes(largestJs.gzipBytes)} gzip / ${formatBytes(
      largestJsBudget,
    )} budget`,
  );
  if (largestJs.gzipBytes > largestJsBudget) {
    failures.push(
      `largest single JS exceeds its gzip budget (${formatBytes(largestJs.gzipBytes)} > ${formatBytes(
        largestJsBudget,
      )})`,
    );
  }
}

if (failures.length > 0) {
  console.error('\nBundle budget check failed.');
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exitCode = 1;
} else {
  console.log('\nBundle budget check passed.');
}
