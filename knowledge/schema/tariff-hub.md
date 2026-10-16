# Tariff Hub database schema

Database `ratehub`, schema `tariff`, PostgreSQL.
Use this when asked to generate SQL INSERT statements for a new carrier.
Never store real carrier or client names in any table except `tariff.carrier.legal_name` (which is filled by hand, never by a script).

---

## Key rule: drafts only
All INSERT statements you produce are DRAFTS for human review. Never say they are ready to run.
Always end with: "These are draft INSERTs. A human must review and approve before running."

---

## Step 1 — always add the carrier first

```sql
INSERT INTO tariff.carrier (carrier_code, carrier_name, status)
VALUES ('<CODE>', '<CODE>', 'ACTIVE');
-- legal_name is filled by hand on the server, never by a script
```

Get `carrier_id` with:
```sql
SELECT carrier_id FROM tariff.carrier WHERE carrier_code = '<CODE>';
```

---

## Ground rates → `tariff.ground_tariff`

One row per price point. Key columns:

| Column | Notes |
|--------|-------|
| `carrier_id` | FK to `tariff.carrier` |
| `carrier_code` | e.g. `B1C06` |
| `carrier_name` | same as code |
| `currency_code` | ISO 3-letter: JPY, EUR, USD |
| `record_type` | `FREIGHT` / `SURCHARGE` / `ACCESSORIAL` / `FUEL_RULE` / `RULE` |
| `service_type` | `LTL` / `FTL` / `GROUPAGE` / `ECONOMY_SELECT` |
| `origin_country_code` | ISO 2-letter |
| `dest_country_code` | ISO 2-letter |
| `origin_city` / `dest_city` | English name |
| `origin_city_local` / `dest_city_local` | Local script (Japanese, etc.) |
| `break_type` | `WEIGHT` / `DISTANCE` / `EQUIPMENT` / `NONE` |
| `weight_from_kg` / `weight_to_kg` | Band (from exclusive, to inclusive) |
| `charge_basis` | `PER_KG` / `PER_100KG` / `PER_SHIPMENT` / `PER_TRUCK` |
| `rate_value` | Rounded to 4 decimal places |
| `min_charge` | Minimum charge |
| `auto_apply` | `TRUE` for surcharges applied automatically |
| `valid_from` / `valid_to` | Date range from the rate card |
| `source_ref` | File name |
| `source_sheet` | Sheet name |
| `source_row` | Row number in the Excel file |
| `status` | `DRAFT` until approved |

Example FREIGHT row:
```sql
INSERT INTO tariff.ground_tariff (
  carrier_id, carrier_code, carrier_name, currency_code,
  record_type, service_type,
  origin_country_code, dest_country_code, dest_city, dest_city_local,
  break_type, weight_from_kg, weight_to_kg,
  charge_basis, rate_value,
  valid_from, source_ref, source_sheet, source_row, status
) VALUES (
  <carrier_id>, 'B1C06', 'B1C06', 'JPY',
  'FREIGHT', 'GROUPAGE',
  'JP', 'JP', 'Kanto', '関東',
  'WEIGHT', 0, 5,
  'PER_SHIPMENT', 578,
  '2026-01-01', 'B1C06_2026 Rates.xlsx', 'Consolidated Heiwajima', 11, 'DRAFT'
);
```

---

## Air rates → `tariff.air_tariff`

One row per lane × service level × weight band. Key columns:

| Column | Notes |
|--------|-------|
| `carrier_id` / `carrier_code` | FK to carrier |
| `currency_code` | ISO 3-letter |
| `origin_airport` / `dest_airport` | IATA 3-letter code (lane carriers) |
| `rate_group` | Zone code (zone carriers like B1C07) |
| `service_level` | SL0=fastest, SL3=slowest |
| `service_type` | DTD / DTA / ATD / ATA (empty = all) |
| `weight_from_kg` / `weight_to_kg` | Band |
| `weight_step_kg` | Round up chargeable weight to this step |
| `rate_value` | Rounded to 2 decimals |
| `rate_value_exact` | Carrier's full figure |
| `valid_from` / `valid_to` | From rate card |
| `source_ref` / `source_sheet` / `source_row` | Traceability |
| `status` | `DRAFT` |

---

## Air zone chart → `tariff.air_zone_master`

For zone-priced air carriers (B1C07 pattern):

| Column | Notes |
|--------|-------|
| `carrier_id` / `carrier_code` | FK |
| `origin_country` / `dest_country` | ISO 2-letter |
| `rate_group` | Zone that joins to `air_tariff.rate_group` |
| `direction` | EXPORT / IMPORT / BOTH |

---

## Ground zone chart → `tariff.ground_zone_master`

For zone-priced ground carriers (B1C06 pattern):

| Column | Notes |
|--------|-------|
| `carrier_id` / `carrier_code` | FK |
| `dest_country_code` | ISO 2-letter |
| `dest_region` | Prefecture / area name |
| `rate_group` | Zone / district name that joins to `ground_tariff` |

---

## Ocean rates → `tariff.ocean_tariff`

One row per lane × equipment × charge line. Key columns:

| Column | Notes |
|--------|-------|
| `carrier_id` / `carrier_code` | FK |
| `origin_port` / `dest_port` | Port code (use LGB-A / LGB-B, never real line name) |
| `equipment_type` | 20GP / 40GP / 40HC / LCL |
| `leg` | ORIGIN / OCEAN / DESTINATION |
| `charge_code` | From `tariff.charge_type` |
| `charge_basis` | PER_CONTAINER / PER_WM |
| `rate_value` | |
| `routing` | PRIMARY / BACKUP |
| `currency_code` | |
| `valid_from` / `valid_to` | |
| `status` | `DRAFT` |

---

## How to generate INSERTs for a new carrier

1. Call `excel_profile` on the file — identify sheet names, weight bands, origin/destination structure.
2. Call `knowledge_search "tariff hub schema"` to load this file.
3. Decide the mode: ground / air / ocean based on the file structure.
4. For each rate row in the file, produce one INSERT with:
   - `status = 'DRAFT'`
   - `source_ref` = file name, `source_sheet` = sheet name, `source_row` = row number
   - All values from the file, not invented
5. Group by carrier first (INSERT into `tariff.carrier`), then rates.
6. End every response with: "These are draft INSERTs. A human must review and approve before running."
