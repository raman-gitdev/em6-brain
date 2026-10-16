# Freight audit and payment

## What freight audit is
Shippers move goods with many carriers. Each carrier has a contract with a tariff (rate card). Every shipment produces an invoice. Freight audit checks that each invoice charges exactly what the contract allows, before it is paid. Freight audit and payment (FAP) companies do this for many clients and carriers at once, and also report spend and data back to the client.

## The basic audit check
For one invoice line the auditor needs:
1. The shipment facts: carrier, service, ship date, origin, destination, pieces, actual weight, dimensions, any special handling (DG, temperature, time-definite).
2. The contracted tariff valid on the ship date.
3. The expected price: chargeable weight -> zone or lane -> weight band -> freight, then minimum, then surcharges (fuel for that week or month) and agreed accessorials.
4. The comparison: billed vs expected, line by line. A difference is an exception to explain or dispute.

## Common billing errors
- Wrong rate: not the contracted price, an expired tariff, or a list price instead of the contract price.
- Wrong zone or lane: destination placed in a more expensive zone.
- Wrong weight: actual weight overstated, volume weight computed with the wrong divisor, chargeable weight rounded wrongly.
- Minimum charge applied when the weight-based price is higher, or the other way round.
- Fuel surcharge: wrong % or wrong week/month, applied to the wrong base, or applied twice.
- Accessorials that were never requested or are not in the contract.
- Duplicate invoices: the same shipment billed twice (same tracking/waybill number, same amount).
- Currency or exchange rate errors; tax added where the contract is tax-exclusive.
- Service mismatch: billed for express when standard was booked.

## Accruals
An accrual is the expected cost of a shipment booked in the accounts before the carrier invoice arrives, so monthly costs are right. When the invoice arrives it is matched to the accrual; differences are investigated. Good tariffs make accruals accurate.

## Data the audit depends on
- Shipment data (often from EDI messages or shipper systems).
- Invoice data (EDI, PDF or Excel from the carrier).
- Tariff data (the rate hub).
If any of the three is missing or wrong, the audit result is wrong. Always say which of the three an answer depends on.
