/*
 *     Copyright (c) 2018 Future Internet Consulting and Development Solutions S.L.
 *
 *     This file is part of Wirecloud Platform.
 *
 *     Wirecloud Platform is free software: you can redistribute it and/or
 *     modify it under the terms of the GNU Affero General Public License as
 *     published by the Free Software Foundation, either version 3 of the
 *     License, or (at your option) any later version.
 *
 *     Wirecloud is distributed in the hope that it will be useful, but WITHOUT
 *     ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 *     FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 *     License for more details.
 *
 *     You should have received a copy of the GNU Affero General Public License
 *     along with Wirecloud Platform.  If not, see
 *     <http://www.gnu.org/licenses/>.
 *
 */

/* globals Wirecloud */


(function (utils) {

    "use strict";

    const OPPOSITE = {
        "right": "left",
        "left": "right"
    };

    var SidebarLayout = function SmartColumnLayout(dragboard, options) {
        options = utils.merge({
            position: "left"
        }, options);

        Wirecloud.ui.SmartColumnLayout.call(this,
                          dragboard,
                          1,
                          12,
                          4,
                          3,
                          12);

        privates.set(this, {
            active: false
        });

        Object.defineProperties(this, {
            position: {
                value: options.position
            },
            active: {
                get: on_active_get,
                set: on_active_set
            }
        });
    };
    utils.inherit(SidebarLayout, Wirecloud.ui.SmartColumnLayout);

    SidebarLayout.prototype.addWidget = function addWidget(widget, affectsDragboard) {
        Wirecloud.ui.DragboardLayout.prototype.addWidget.call(this, widget, affectsDragboard);

        if (this.icon == null) {
            let handle = document.createElement("div");
            let icon = document.createElement("i");
            //icon.className = "fa fa-caret-" + OPPOSITE[this.position];
            icon.className = "fa " + (this.position === "right" ? "fa-caret-left" : "fa-search");
            handle.appendChild(icon);
            handle.addEventListener("click", () => {
                this.active = !this.active;
            });
            handle.className = "wc-sidebar-" + this.position + "-handle";
            widget.wrapperElement.appendChild(handle);
            this.icon = icon;
        }
    };

    SidebarLayout.prototype.getWidth = function getWidth() {
        return 497;
    };

    SidebarLayout.prototype.updatePosition = function updatePosition(widget, element) {
        var tmp;
        if (!(this.dragboard.tab.workspace.editing || this.active)) {
            tmp = -this.getWidth() - this.leftMargin + this.dragboardLeftMargin;
        } else {
            tmp = 0;
        }

        if (this.position === "left") {
            element.style.left = tmp + "px";
            element.style.right = "";
        } else {
            element.style.right = tmp + "px";
            element.style.left = "";
        }
    };

    Wirecloud.ui.SidebarLayout = SidebarLayout;

    const privates = new WeakMap();

    const on_active_get = function on_active_get() {
        return privates.get(this).active;
    };

    const on_active_set = function on_active_set(newstatus) {
        privates.get(this).active = newstatus;

        if (this.position === "left") {
            this.icon.className = "fa fa-search";
        } else {
            let position = this.active ? this.position : OPPOSITE[this.position];
            this.icon.className = "fa fa-caret-" + position;
        }

        this._notifyWindowResizeEvent(true, true);
    };

})(Wirecloud.Utils);
