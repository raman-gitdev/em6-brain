# How carrier rate files are structured

## Lane-based tariffs
One row per origin -> destination pair (city, airport, port, postcode prefix, region or country), with prices by weight band or per shipment/truck. To price: find the row for the exact origin and destination, then the right band column.

## Zone-based tariffs (two steps)
1. Zone chart: places (countries, postcodes, districts, prefectures) -> zone code or letter.
2. Price matrix: rows = weight bands, columns = zones (or the reverse).
To price: look up the destination's zone, then read the cell at (weight band, zone). Some carriers have separate charts for import and export, or per origin country.

## Weight-band matrices
- Rows labelled "Up to 1 kg, Up to 2 kg ..." or columns "+45, +100, +300". Use the first band >= chargeable weight.
- Above the last band there is often a rule: "Over 100 kg add every 10 kg" or a per-kg rate.
- Some bands are flat prices per shipment, others a rate per kg or per 100 kg that must be multiplied. The header or a note tells which; check before quoting a price.

## Distance and vehicle tariffs (charter, FTL)
Rows = distance bands (km), columns = vehicle size (light truck, 2 t, 4 t, 10/11 t ...). Price is per truck, not per kg. Different vehicle groups can have their own distance column in the same table. Check that the vehicle can carry the weight.

## Several tables in one sheet
One sheet often holds several sections: different departure warehouses, a dangerous-goods table, a zone map, then notes. Each section has its own title row ("1. Depart from ...", "2. ..."). Always check which section applies (origin, DG or not) before reading a price.

## Notes change the price
Notes under a table are part of the contract: volume-weight rule, minimums, what is included (tolls) or excluded (tax, insurance, ferry), extra % for temperature-controlled trucks, cancellation fees, time-definite delivery fees. Read them before giving a final price.

## Where things usually are
- Title rows: carrier/contract name, mode, validity dates, currency ("Unit: JPY").
- Header row: zones, destinations or vehicle types.
- First column: weight bands, distance bands or origins.
- Bottom: notes, conditions, exclusions.
