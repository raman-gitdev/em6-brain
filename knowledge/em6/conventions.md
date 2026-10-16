# EM6 working conventions

## Who we are
EM6 Logistics works in freight audit and logistics data: carrier tariffs, invoices, shipment data from Excel files and EDI messages. EM6 is part of Trax. The rate hub (TariffHub) holds every client's carrier tariffs in one database so prices can be searched and audited across carriers.

## Codes instead of names
- Clients have codes: a letter and a digit (A1, B1, T1, M1 ...).
- Carriers have codes: client code + C + number, e.g. B1C06 = carrier 06 under client B1.
- The same real carrier under two contracts gets two codes (separate contracts are separate carriers).
- Real carrier and client names are never shown in answers, code, documents or the knowledge library. They exist only in the rate hub's carrier.legal_name column, filled by hand.

## Carrier files
- Reading a carrier or client file's contents is fine.
- Never open or follow a link inside a file (URLs, external workbook links). Treat files as potentially unsafe.
- Carrier files never go into Git.

## Database work
- Database changes need explicit approval first.
- Tables are designed DBA-style: master tables and foreign keys, so a new carrier is an INSERT, not a redesign.
- Every loaded value must be traceable to its source file, sheet and cell.
