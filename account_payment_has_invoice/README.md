# Account Payment Has Invoice (Odoo 16)

Adds a computed, stored checkbox on payments to indicate if they are linked to one or more invoices. The checkbox is displayed in the payment list (tree) view.

## Features

- New boolean field `has_invoice` on `account.payment`.
- Computed from `invoice_ids` and stored (stored=True) for fast search, filter, and group by.
- Injected into the payment tree view (`account.view_account_payment_tree`) as a read-only boolean toggle column.
- Automatically updates when invoices are linked or unlinked from the payment.

## Installation

1. Add this module folder (`account_payment_has_invoice`) to your Odoo addons path.
2. Update the app list and install the module from Apps.

## Notes

- The field is computed based on the standard `invoice_ids` relation on payments. If a payment is linked to one or more invoices, the checkbox appears checked.
- The field is stored and indexed to support search and grouping in list view.
