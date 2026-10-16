# How to classify a carrier tariff file

## Steps for a new file or a batch of files
1. Profile every file (excel_profile). Note mode (air or ground), currency, validity, sheets and their sections.
2. Decide what the rows and columns are. Look at the header row and the first column of each price table:
   - places on both sides (origin and destination named per row) -> LANE pattern
   - zone codes or letters in the header + a separate chart that maps places to zones -> ZONE pattern
   - countries on both sides -> COUNTRY-TO-COUNTRY pattern
   - airport codes (3 letters) on both sides -> AIRPORT-TO-AIRPORT pattern
   - distance (km) and vehicle sizes -> CHARTER / VEHICLE pattern
   - postcodes or postcode prefixes -> POSTCODE pattern
   - only weight bands, no places -> PARCEL / FLAT pattern
3. Search the pattern catalogue (knowledge_search with the pattern name, e.g. "air zone pattern") to see how EM6 already loads it.
4. Answer per file: pattern name, the evidence cells (sheet + cell) that show it, which existing approach fits, and what does not fit yet.
5. Several files with the same layout (same headers, same sections) = same pattern; say so once and list the files.

## What to tell the user
- "Fits the current approach": name the tables it loads into (air_tariff, ground_tariff, zone master, air_transit, air_accessorial) and the point type used.
- "Partly fits": say exactly what is new (an unknown charge basis, a new point type, a rule the masters don't have) and give 2-3 options: (a) map it to an existing master code, (b) add a master code (needs approval), (c) store it as a RULE / SURCHARGE row, (d) new table or column (needs DB approval).
- Never propose changing the database directly. Database changes need explicit approval; the brain only drafts.

## Point types in the rate hub
CITY, POSTCODE, REGION, PROVINCE, COUNTRY, ZONE, AIRPORT. A lane only answers a question asked in its own terms.

## Record types in the rate hub
FREIGHT (produces a price), SURCHARGE, ACCESSORIAL, RULE (e.g. weight adders, "over 100 kg add every 10 kg").
