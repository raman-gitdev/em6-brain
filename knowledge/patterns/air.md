# Air tariff patterns

## Air zone pattern (zone-wise tariff)
Recognise by: per-country cards or sheets; a zone chart that maps destination countries to zone codes; a price matrix with weight bands down and zones across; separate export and import tables.
Example carrier: B1C07.
Loads into: air_zone_master (origin/destination -> rate_group) and air_tariff (rate_group, weight band, service). Point type ZONE.
Watch out:
- Import pricing can need two zones: the origin zone x the local destination zone gives the rate_group.
- Weight step: many cards round chargeable weight up to the next half kg (weight_step).
- Currency can differ per country card; keep it per row.
- Bands above the last row are often per-kg rates, not per-shipment prices.

## Air country-to-country pattern (with key lanes)
Recognise by: origin country rows and destination country columns (or a list of country pairs); door-to-door prices; often a second section of "key lanes" city -> city.
Example carriers: A1C10, A1C13, A1C14.
Loads into: air_tariff with point type COUNTRY; key lanes as CITY lanes; area names through city_area; business split through client_business (codes A1B01-A1B20).
Watch out:
- Key lanes are per business unit and can carry deck (LD lower deck / UD upper deck) and handling codes.
- Country prices are door-to-door; other services are derived: DA and AD about 6% less, AA about 12% less (check the file's own note).
- Large countries (e.g. US, China) may be split into zones inside the country.

## Air airport-to-airport pattern (lane / bid template)
Recognise by: rows with origin airport and destination airport (3-letter codes), weight break columns (+45, +100, +300 ...), service level columns or rows, transit time columns; often a customer bid template.
Example carriers: B1C08, B1C09, B1C10, B1C11.
Loads into: air_tariff (lane rows, point type AIRPORT), air_transit (airport pair, service, transit hours), air_accessorial (once per lane or carrier-wide).
Watch out:
- Service levels SL0-SL3 (carrier-specific meaning); check the file legend.
- Transit is given in days or hours; store hours.
- Fuel is separate: weekly or monthly published %, or a jet-fuel index method (carrier_fuel_rule).
- Accessorials repeat on every row in the file but are loaded once per lane.

## Air zone + postcode pattern
Recognise by: a zone chart where some countries are split by postcode ranges.
Example carrier: T1C12 (postcode ranges for DE, FR, RU).
Loads into: air_zone_master with postcode from/to ranges, then air_tariff by rate_group.
