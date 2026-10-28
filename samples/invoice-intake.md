# Supplier invoice intake

*Synthetic description written for demos. Any resemblance to a real company is accidental.*

## Context
The Accounts Payable team of Acme Synthetic Co. receives about 1,200 invoices per month from roughly 300 suppliers.
Invoices arrive as PDF attachments in a shared Outlook mailbox; a few still come on paper and are scanned.
Each invoice takes around 14 minutes of analyst time from download to ERP entry.

## Current steps
An analyst downloads each attachment manually and saves it in a SharePoint folder.
The analyst classifies the invoice as goods, services or utilities and routes it to the analyst who handles that category.
Invoice fields such as supplier tax id, number, dates, totals and line items are typed by hand from the PDF.
The analyst checks the invoice against the purchase order and the goods receipt using a fixed checklist with a 2% price tolerance.
Mismatches above the tolerance go to the budget owner, who approves or rejects the exception.
Approved invoices are entered manually into the SAP ERP, field by field.
Treasury schedules the payment run automatically every Tuesday through the ERP.
Finally the analyst sends an e-mail confirmation to the supplier with the expected payment date.

## Pain points
About 18% of invoices are returned for rework because of typing errors or wrong routing.
The matching rules are standard and have not changed in the last two years.
The ERP exposes an API for creating supplier invoices, but it is not used today.
Internal audit reviews a sample of exceptions every quarter for fraud and compliance.
