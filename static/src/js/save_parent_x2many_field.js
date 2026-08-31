/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    X2ManyField,
    x2ManyField,
} from "@web/views/fields/x2many/x2many_field";

export class SaveParentX2ManyField extends X2ManyField {
    async onAdd(params = {}) {
        const saved = await this.props.record.save();
        if (!saved || !this.props.record.resId) {
            return;
        }

        const context = {
            ...(params.context || {}),
            default_recorrido_id: this.props.record.resId,
        };
        return super.onAdd({ ...params, context });
    }
}

registry.category("fields").add("save_parent_one2many", {
    ...x2ManyField,
    component: SaveParentX2ManyField,
});
