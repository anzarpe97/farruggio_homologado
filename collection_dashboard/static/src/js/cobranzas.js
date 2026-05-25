odoo.define('collection_dashboard.dashboard', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    // Inject CSS from JS so colors can be controlled here
    (function insertCollectionDashboardStyles() {
        var styleId = 'collection-dashboard-injected-styles';
        if (document.getElementById(styleId)) {
            return; // already injected
        }
        var css = '\n'
            + '/* Injected by collection_dashboard static/js/cobranzas.js */\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.status-overdue-critical { background: #ef4444 !important; border-left: 4px solid #ffffff; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.status-overdue-warning { background: #f59e0b !important; border-left: 4px solid #f59e0b; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.status-current { background: #10b981 !important; border-left: 4px solid #10b981; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.status-overdue-critical td, .modern-dashboard-tree .o_list_table tbody tr.status-overdue-warning td, .modern-dashboard-tree .o_list_table tbody tr.status-current td { color: #000000ff !important; font-weight: 700 !important; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.text-danger { background: #ff9688 !important; border-left: 4px solid #ffffff; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.text-warning { background: #f3c87eff !important; border-left: 4px solid #f59e0b; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.text-success { background: #8bfdd7ff !important; border-left: 4px solid #10b981; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-tree .o_list_table tbody tr.text-danger td, .modern-dashboard-tree .o_list_table tbody tr.text-warning td, .modern-dashboard-tree .o_list_table tbody tr.text-success td { color: #000000ff !important; font-weight: 700 !important; }\n'
            + '.modern-dashboard-kanban .status-overdue-critical { background: #ef4444 !important; border-left: 4px solid #ffffff; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-kanban .status-overdue-warning { background: #f59e0b !important; border-left: 4px solid #f59e0b; color: #000000ff; font-weight: 700; }\n'
            + '.modern-dashboard-kanban .status-current { background: #10b981 !important; border-left: 4px solid #10b981; color: #000000ff; font-weight: 700; }\n'
            + '.status-icon { color: #000000ff !important; margin-right: 0.5rem; }\n';

        var style = document.createElement('style');
        style.id = styleId;
        style.type = 'text/css';
        style.appendChild(document.createTextNode(css));
        document.getElementsByTagName('head')[0].appendChild(style);
    })();

    ListRenderer.include({
        // The tree view already sets class="modern-dashboard-tree" in XML; no start override required.

        _renderRow: function (record) {
            var $row = this._super.apply(this, arguments);
            
            var estado = record.data.estado;
            var dias = record.data.dias || record.data.days_since_issue;
            var plazo = (record.data.plazo_dias !== undefined && record.data.plazo_dias !== null)
                ? record.data.plazo_dias
                : null;

            // Remover todas las clases de estado anteriores (incluyendo decoraciones nativas)
            $row.removeClass('status-overdue-critical status-overdue-warning status-overdue-medium status-current text-danger text-warning text-success');

            // Remover íconos anteriores si existen
            $row.find('.status-icon').remove();

            function addStatusClass(cls, icon, title, variant) {
                $row.addClass(cls);
                // Also add Odoo decoration classes so theme rules that target .text-danger/.text-warning work
                if (cls.indexOf('critical') !== -1) {
                    $row.addClass('text-danger');
                } else if (cls.indexOf('warning') !== -1) {
                    $row.addClass('text-warning');
                } else if (cls.indexOf('current') !== -1) {
                    $row.addClass('text-success');
                }
                var $firstCell = $row.children('td.o_data_cell:visible').first();
                if ($firstCell.length) {
                    $firstCell.prepend(
                        '<i class="fa ' + icon + ' status-icon ' + (variant || '') + '" title="' + title + '"></i>'
                    );
                }
            }

            // Aplicar clases según el estado
            if (estado === 'moroso') {
                addStatusClass('status-overdue-critical', 'fa-exclamation-triangle', 'Moroso', 'critical');
            } else if (estado === 'critico') {
                addStatusClass('status-overdue-critical', 'fa-exclamation-circle', 'Crítico', 'critical');
            } else if (estado === 'vencido') {
                addStatusClass('status-overdue-warning', 'fa-clock-o', 'Vencido', 'warning');
            } else if (estado === 'a_vencer') {
                addStatusClass('status-current', 'fa-check-circle', 'A Vencer', 'current');
            } else {
                // Lógica de respaldo basada en días y plazo
                if (typeof dias === 'number' && typeof plazo === 'number') {
                    var diasMora = dias - plazo;
                    
                    if (diasMora >= 31) {
                        addStatusClass('status-overdue-critical', 'fa-exclamation-triangle', 'Moroso', 'critical');
                    } else if (diasMora >= 20) {
                        addStatusClass('status-overdue-critical', 'fa-exclamation-circle', 'Crítico', 'critical');
                    } else if (diasMora >= 1) {
                        addStatusClass('status-overdue-warning', 'fa-clock-o', 'Vencido', 'warning');
                    } else {
                        addStatusClass('status-current', 'fa-check-circle', 'A Vencer', 'current');
                    }
                }
            }
            
            return $row;
        },

        _renderHeader: function() {
            var $header = this._super.apply(this, arguments);
            $header.addClass('modern-table-header');
            return $header;
        }
    });

    // The kanban view already sets class="modern-dashboard-kanban" in XML; no runtime change needed.
});