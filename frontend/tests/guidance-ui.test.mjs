import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('crop detail presents every deterministic guidance field', () => {
  const source = fs.readFileSync('src/app/crops/[id]/CropDetailClient.tsx', 'utf8');
  for (const field of [
    'action_plan', 'risk_notes', 'water_plan', 'management_guidance',
    'check_before_planting', 'first_test', 'planting_window', 'major_risk',
    'soil_health_practices', 'rotation_guidance',
  ]) assert.match(source, new RegExp(`crop\\.${field}|crop\\.[a-z_]+\\.${field}`));
});

test('results explain confidence and detailed source provenance', () => {
  const source = fs.readFileSync('src/components/LandSummary.tsx', 'utf8');
  for (const field of [
    'available_factor_names', 'missing_factor_names', 'data_status',
    'county_history_status', 'partial', 'data_period', 'geographic_level',
    'limitations',
  ]) assert.match(source, new RegExp(field));
  assert.match(source, /extensionUrl\(source\.url/);
});
