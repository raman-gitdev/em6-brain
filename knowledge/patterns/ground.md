# Ground tariff patterns

## Ground city-to-city lane pattern
Recognise by: rows with origin city and destination city, prices per shipment or per weight band; sometimes a second section of dedicated trucks by province and km band.
Example carrier: A1C02.
Loads into: ground_tariff, point type CITY (truck part: PROVINCE lanes + km band, equipment_type).
Watch out: a city search does not match province lanes; vehicle payload (equipment_type max payload) must fit the weight.

## Ground postcode-prefix LTL pattern
Recognise by: origin/destination postcode prefixes (2-3 digits); per-shipment price bands for small weights then a rate per 100 kg; ADR / dangerous goods surcharge %.
Example carrier: A1C01 (per-shipment bands up to 300 kg, then per 100 kg; ADR 10% with a maximum).
Loads into: ground_tariff, point type POSTCODE; ADR as SURCHARGE rows.

## Ground region-to-region pattern
Recognise by: region names on both sides (not cities, not postcodes).
Example carrier: A1C03.
Loads into: ground_tariff, point type REGION.

## Ground district x weight pattern (domestic zone)
Recognise by: destination district columns, weight band rows ("Up to 1 kg" ... "Up to 100 kg", "Over 100 kg add every 10 kg"), a district map (district -> prefectures), one sheet per departure warehouse, a dangerous-goods section.
Example carrier: B1C06.
Loads into: ground_zone_master (prefecture -> district = rate_group), ground_tariff per origin warehouse; the "over 100 kg" line as a RULE row (step pricing). DG table as its own rows (separate service or flag).
Watch out: same layout on several sheets = same pattern, different origin.

## Ground charter (km x vehicle) pattern
Recognise by: distance band rows (km), vehicle columns (light truck, 2 t, 4 t, 11 t), price per truck; "over 500 km add per +50 km".
Example carriers: B1C06 (Charter sheet), B1C11 (vehicle per lane).
Loads into: ground_tariff with load_type FTL / charter, equipment_type per vehicle, charge_basis per truck; the per +50 km adder as a RULE row.
Watch out: different vehicle groups can have their own distance label column in the same table; % adders for refrigerated trucks are SURCHARGE rows.

## Ground parcel pattern
Recognise by: only weight (or size) bands and prices, no zone chart and no places, or a single national price.
Example carriers: B1C05, T1C12 (Standard parcel).
Loads into: ground_tariff with load_type parcel, one lane (country or ALL).

## Step pricing and bands (all ground)
- Step: price = base_amount + ceil((kg - band from) / step) x rate.
- Pallet bands: price by number of pallets (piece_type).
- Always check the vehicle can carry the weight (payload check).
