# Glossary (full)

Full version of the core glossary. Words in rate files and questions often differ; each group is the same idea.

## Places
- ORIGIN = from, ship from, depart from, departure place, pickup, collection, shipper, consignor, sender, POL (port of loading), airport of departure.
- DESTINATION = to, ship to, deliver to, delivery, consignee, receiver, POD (port of discharge), airport of destination. In domestic tariffs a "district", "region", "area" or "zone" column usually means the destination.
- Warehouse = W/H, depot, DC, hub, facility. "Depart from: <warehouse>" names the origin of that table.
- Lane = one origin -> destination pair. Zone = a group of places that share one price. A zone chart maps places to zones; a price matrix maps zones x weights to prices.

## Weight and size
- Actual weight = gross weight on the scale.
- Volume weight (volumetric, dimensional) = L x W x H in cm / divisor. Common divisors: air 6000 (1 cbm = 167 kg), express/courier 5000 (1 cbm = 200 kg); road often 1 cbm = 250-333 kg; sea LCL 1 cbm = 1000 kg (W/M). The carrier's own rule in the file always wins.
- Chargeable weight = the greater of actual and volume weight, then rounded up per the carrier's rule (e.g. to the next 0.5 kg).
- Weight break / band: "Up to 10 kg", "0-100 kg", "+45", "+100". Pick the first band whose upper limit is >= the chargeable weight.
- "Over 100 kg, add every 10 kg" = for each extra 10 kg (or part) above the last band, add that amount.
- Minimum (min charge) = the lowest amount charged, whatever the weight.

## Price basis
- per shipment / consignment, per kg, per 100 kg, per pallet, per cbm, per truck or vehicle, per km, per container (20', 40', 40'HC), flat rate.
- Step pricing = base price plus a rate per step (per km band, per extra kg).

## Modes and loads
- FTL = full truckload (whole truck, priced per truck). LTL = less than truckload = groupage = consolidated (shared truck, priced by weight).
- Charter = a dedicated vehicle booked for one job, usually priced by distance and truck size.
- Express / courier / parcel = small fast shipments, zone x weight pricing.
- Air freight = general cargo by air. Sea FCL = full container, LCL = shared container.

## Services (EM6: service codes are carrier-specific)
- DTD door-to-door, DTA door-to-airport, ATA airport-to-airport, ATD airport-to-door.
- Transit time = promised travel time (days or hours).

## Charges
- Freight = the base transport price.
- Surcharge = an extra on top of freight: fuel (FSC, BAF), dangerous goods, peak season, security.
- Accessorial = an extra service: pickup, tail-lift, waiting time, residential, remote area (ODA), customs clearance, packing.
- Fuel surcharge is either a % of freight or an amount per kg, and changes weekly or monthly.
- DG = dangerous goods (hazmat; ADR by road, IATA DGR by air). Often priced in its own table.
- Tax and insurance are usually NOT included unless the file says so.

## Documents and work
- Tariff = rate card = rate sheet = price list = exhibit / schedule of a carrier contract.
- Validity = effective date, valid from / to. A rate only applies to shipments in its validity.
- Invoice = what the carrier bills. Freight audit = checking each invoice against the contracted tariff.
- Accrual = expected freight cost booked before the invoice arrives.
- Incoterms (EXW, FCA, DAP, DDP ...) decide which party pays which part of the journey.
