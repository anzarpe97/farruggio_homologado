/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";

const { onMounted } = owl;

class InvoiceListController extends ListController {
    setup() {
        super.setup();

        onMounted(() => {
            this.renderApproveButton();
        });
    }

    async renderApproveButton() {
        const target = document.querySelector(
            "body > div.o_action_manager > div > div.o_control_panel > div.o_cp_bottom > div.o_cp_bottom_left"
        );

        if (!target || this.props.modelName !== "account.move") {
            return;
        }

        // Crear el botón
        const button = document.createElement("button");
        button.innerHTML = "Aprobar Facturas";
        button.classList.add("btn", "btn-primary", "me-2");
        button.style.marginLeft = "10px";

        button.onclick = async () => {
            const selected = this.model.root.selection;
            if (!selected.length) {
                this.env.services.notification.add("Selecciona al menos una factura.", {
                    type: "warning",
                });
                return;
            }

            const ids = selected.map((record) => record.resId);
            await this.rpc("/approve/invoices", { ids });

            // recargar vista
            this.model.load();
        };

        // Evita duplicados
        if (!target.querySelector(".btn-approve-invoice")) {
            button.classList.add("btn-approve-invoice");
            target.appendChild(button);
        }
    }
}

registry.category("views").add("account.move_list_approve_button", {
    ...registry.category("views").get("list"),
    Controller: InvoiceListController,
});
