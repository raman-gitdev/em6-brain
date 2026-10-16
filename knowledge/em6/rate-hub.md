# The EM6 rate hub (TariffHub)

## What it is
An internal web app with a PostgreSQL database (database ratehub, schema tariff) that stores carrier tariffs from many clients in one unified form, so a user can search a shipment and see prices from several carriers side by side. One table per mode: ground_tariff and air_tariff.

## Lane carriers vs zone carriers
- Lane carriers price a specific pair (city, airport, postcode prefix, region, country -> same). Rows hold the lane directly. For air lane carriers, air_transit holds the airport pair, service and transit hours.
- Zone carriers price by zone. A zone master (air_zone_master, ground_zone_master) turns origin + destination (country, area or postcode range) into a rate_group; the tariff row is found by rate_group, weight band and service.
- Point types: CITY, POSTCODE, REGION, PROVINCE, COUNTRY, ZONE, AIRPORT. A lane only answers a question asked in its own terms (a city search does not match province lanes).

## Main tables
- carrier: carrier master (code, fuel method, notes; legal_name back end only).
- Masters (allowed codes): service_type, service_level, charge_type, airport, load_type, equipment_type (with max payload), charge_basis, piece_type, client_business, city_area.
- ground_tariff, air_tariff: freight rows. record_type FREIGHT produces a price; SURCHARGE, ACCESSORIAL, RULE (e.g. weight adders) modify it.
- air_accessorial: air extra charges per lane or carrier-wide.
- Fuel: carrier_fuel_rule, carrier_fuel_published, fuel_index, fuel_index_daily, fuel_matrix, fiscal_calendar, fuel_period; functions fuel_charge() and fuel_matrix_value().

## How a price is found (air)
1. Chargeable weight = higher of actual and volume weight, raised to the minimum chargeable weight and rounded up to the carrier's weight step.
2. Place -> price group: zone carriers via the zone master; lane carriers via the airport pair.
3. Freight row for carrier, rate group or lane, service, level, weight band and ship date (valid_from to valid_to).
4. Add fuel for the ship date (published % or jet-fuel index method) and the accessorials that apply.

## How a price is found (ground)
Lane or zone -> load type (parcel, LTL, FTL ...) -> vehicle that can carry the weight -> band (weight, pallets or km) -> charge basis (per kg, per shipment, per truck, step) -> minimum -> surcharges and fuel rows.

## Service codes
Service types (DTD, DTA, ATA, ATD, express codes) and service levels are carrier-specific: the same code can mean different things for different carriers.
