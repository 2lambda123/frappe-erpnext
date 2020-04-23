{% include "erpnext/selling/page/point_of_sale_beta/pos_item_selector.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_item_cart.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_item_details.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_payment.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_number_pad.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_past_order_list.js" %}
{% include "erpnext/selling/page/point_of_sale_beta/pos_past_order_summary.js" %}

erpnext.PointOfSale.Controller = class {
    constructor(wrapper) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = wrapper.page;

		this.initialize_assets();
	}

	initialize_assets() {
		const assets = [
			'assets/erpnext/js/pos/clusterize.js',
			'assets/erpnext/css/pos-beta.css'
		];

		frappe.require(assets, this.check_opening_voucher.bind(this));
	}

	check_opening_voucher() {
		return frappe.call("erpnext.selling.page.point_of_sale.point_of_sale.check_opening_voucher", { "user": frappe.session.user })
			.then((r) => {
				if (r.message && r.message.length === 1) {
					// assuming only one opening voucher is available for the current user
					this.initialize_app(r.message[0]);
				} else {
					this.create_opening_voucher();
				}
			})
	}

	create_opening_voucher() {
		const on_submit = ({ company, pos_profile, custody_amount }) => {
			frappe.dom.freeze();

			return frappe.call("erpnext.selling.page.point_of_sale.point_of_sale.create_opening_voucher", 
				{ pos_profile, company, custody_amount })
				.then((r) => {
					frappe.dom.unfreeze()
					if (r.message) {
						this.initialize_app(r.message);
					}
				})
		}

		frappe.prompt([
			{
				fieldtype: 'Link', label: __('Company'), default: frappe.defaults.get_default('company'),
				options: 'Company', fieldname: 'company', reqd: 1
			},
			{
				fieldtype: 'Link', label: __('POS Profile'),
				options: 'POS Profile', fieldname: 'pos_profile', reqd: 1
			},
			{
				fieldtype: 'Currency', options: 'company:company_currency',
				label: __('Amount in custody'), fieldname: 'custody_amount', reqd: 1
			}
		],
		on_submit, __('Create POS Opening Entry'));
	}

	initialize_app(data) {
		this.pos_opening = data.name;
		this.company = data.company;
		this.pos_profile = data.pos_profile;

		this.page.set_title_sub(
			`<span class="indicator orange">
				<a class="text-muted" href="#Form/POS%20Opening%20Voucher/${this.pos_opening}">
					Opened at ${moment(data.period_start_date).format("Do MMMM, h:mma")}
				</a>
			</span>`);

		this.make_app();
	}

	make_app() {
		return frappe.run_serially([
			() => frappe.dom.freeze(),
			() => {
				this.prepare_dom();
				this.initialize_components();
				this.prepare_menu();
			},
			() => this.make_new_invoice(),
			() => frappe.dom.unfreeze(),
			() => this.page.set_title(__('Point of Sale Beta')),
		]);
	}

	prepare_dom() {
		this.wrapper.append(`
			<div class="app grid grid-cols-10 pt-8 gap-6"></div>`
		);

		this.$components_wrapper = this.wrapper.find('.app');
	}

	initialize_components() {
		this.initialize_item_selector();
		this.initialize_item_details();
		this.initialize_item_cart();
		this.initialize_payments();
		this.initialize_past_order_list();
		this.initialize_past_order_summary();
	}

	prepare_menu() {
		var me = this;
		this.page.clear_menu();

		this.page.add_menu_item(__("Form View"), function () {
			frappe.model.sync(me.frm.doc);
			frappe.set_route("Form", me.frm.doc.doctype, me.frm.doc.name);
		});

		this.page.add_menu_item(__("Show Recent Orders"), () => {
			const show = this.order_summary.$component.hasClass('d-none');
			this.toggle_past_order_list(show);
		});

		this.page.add_menu_item(__("Save as Draft"), () => {
			this.frm.save(undefined, undefined, undefined, () => {
				frappe.show_alert({
					message:__("There was an error saving the document."), 
					indicator:'red'
				});

			}).then(() => {
				frappe.run_serially([
					() => frappe.dom.freeze(),
					() => this.make_new_invoice(),
					() => this.cart.load_cart_data_from_invoice(),
					() => frappe.dom.unfreeze(),
				]);
			})
		});

		this.page.add_menu_item(__('Close the POS'), () => {
			var voucher = frappe.model.get_new_doc('POS Closing Entry');
			voucher.pos_profile = me.frm.doc.pos_profile;
			voucher.user = frappe.session.user;
			voucher.company = me.frm.doc.company;
			voucher.pos_opening_voucher = this.pos_opening;
			voucher.period_end_date = frappe.datetime.now_datetime();
			voucher.posting_date = frappe.datetime.now_date();
			frappe.set_route('Form', 'POS Closing Entry', voucher.name);
		});
	}

	initialize_item_selector() {
		this.item_selector = new erpnext.PointOfSale.ItemSelector({
			wrapper: this.$components_wrapper,
			pos_profile: this.pos_profile,
			events: {
				item_selected: args => this.on_cart_update(args),

				get_frm: () => this.frm || {},
			}
		})
	}

	initialize_item_cart() {
		this.cart = new erpnext.PointOfSale.ItemCart({
			wrapper: this.$components_wrapper,
			events: {
				get_frm: () => this.frm,

				cart_item_clicked: (item_code, batch_no) => this.toggle_item_details(item_code, batch_no),

				numpad_event: (value, action) => this.update_item_field(value, action),

				checkout: () => this.payment.render_payment_section(),

				edit_cart: () => this.payment.hide_payment_section()
			}
		})
	}

	initialize_item_details() {
		this.item_details = new erpnext.PointOfSale.ItemDetails({
			wrapper: this.$components_wrapper,
			events: {
				get_frm: () => this.frm,

				toggle_item_selector: (minimize) => {
					this.item_selector.resize_selector(minimize, 'item_details');
					this.cart.toggle_numpad(minimize);
				},

				form_updated: async (cdt, cdn, fieldname, value) => {
					const item_row = frappe.model.get_doc(cdt, cdn);
					if (item_row && item_row[fieldname] != value) {

						if (fieldname === 'qty' && flt(value) <= 0) {
							this.remove_item_from_cart();
							return;
						}

						const { item_code, batch_no } = this.item_details.current_item;
						const event = {
							field: fieldname,
							value,
							item: { item_code, batch_no }
						}
						return this.on_cart_update(event)
					}
				},

				item_field_focused: (fieldname) => {
					this.cart.toggle_numpad_field_edit(fieldname);
				},
				set_batch_in_current_cart_item: (batch_no) => {
					this.cart.update_batch_in_cart_item(batch_no, this.item_details.current_item);
				},
				clone_new_batch_item_in_frm: (batch_serial_map, current_item) => {
					Object.keys(batch_serial_map).forEach(batch => {
						const { item_code, batch_no } = current_item;
						const item_to_clone = this.frm.doc.items.find(i => i.item_code === item_code && i.batch_no === batch_no);
						const new_row = this.frm.add_child("items", { ...item_to_clone });
						// update new serialno and batch
						new_row.batch_no = batch;
						new_row.serial_no = batch_serial_map[batch].join(`\n`);
						new_row.qty = batch_serial_map[batch].length;
						this.frm.doc.items.forEach(row => {
							if (item_code === row.item_code) {
								this.update_cart_html(row);
							}
						});
					})
				}
			}
		});
	}

	initialize_payments() {
		this.payment = new erpnext.PointOfSale.Payment({
			wrapper: this.$components_wrapper,
			events: {
				get_frm: () => this.frm || {},

				toggle_other_sections: (show) => {
					if (show) {
						this.item_details.$component.hasClass('d-none') ? '' : this.item_details.$component.addClass('d-none');
						this.item_selector.$component.addClass('d-none');
					} else {
						this.item_selector.$component.removeClass('d-none');
					}
				},

				submit_invoice: () => {
					this.frm.savesubmit()
						.then((r) => {
							this.set_invoice_status();
							this.enable_disable_components(true);
							this.order_summary.toggle_component(true);
							this.order_summary.show_post_submit_summary_of(this.frm.doc);
							frappe.show_alert({
								indicator: 'green',
								message: __(`POS invoice ${r.doc.name} created succesfully`)
							});
						})
				}
			}
		});
	}

	initialize_past_order_list() {
		this.past_order_list = new erpnext.PointOfSale.PastOrderList({
			wrapper: this.$components_wrapper,
			events: {
				open_invoice_data: (name) => {
					frappe.db.get_doc('POS Invoice', name).then((doc) => {
						this.order_summary.load_summary_of(doc);
					});
				}
			}
		})
	}

	initialize_past_order_summary() {
		this.order_summary = new erpnext.PointOfSale.PastOrderSummary({
			wrapper: this.$components_wrapper,
			events: {
				get_frm: () => this.frm,

				process_return: (name) => {
					this.past_order_list.toggle_component(false);
					frappe.db.get_doc('POS Invoice', name).then((doc) => {
						frappe.run_serially([
							() => this.make_return_invoice(doc),
							() => this.cart.load_cart_data_from_invoice(),
							() => this.cart.$component.removeClass('d-none'),
							() => this.item_selector.$component.removeClass('d-none')
						]);
					});
				},
				edit_order: (name) => {
					this.past_order_list.toggle_component(false);
					frappe.db.get_doc('POS Invoice', name).then((doc) => {
						frappe.run_serially([
							() => (this.frm.doc = doc),
							() => this.cart.load_cart_data_from_invoice(),
							() => this.cart.$component.removeClass('d-none'),
							() => this.item_selector.$component.removeClass('d-none')
						]);
					});
				},
				new_order: () => {
					frappe.run_serially([
						() => frappe.dom.freeze(),
						() => this.cart.$component.removeClass('d-none'),
						() => this.item_selector.$component.removeClass('d-none'),
						() => this.make_new_invoice(),
						() => this.cart.load_cart_data_from_invoice(),
						() => frappe.dom.unfreeze(),
					]);
				}
			}
		})
	}

	toggle_past_order_list(show) {
		this.enable_disable_components(show);
		this.past_order_list.toggle_component(show);
		this.order_summary.toggle_component(show);
	}

	enable_disable_components(disable) {
		if (disable) {
			this.item_selector.disable_selector();
			this.cart.disable_cart();
			this.item_details.disable_item_details();
			this.payment.disable_payments();
		} else {
			this.cart.$component.removeClass('d-none');
			this.item_selector.$component.removeClass('d-none');
		}
	}

	make_new_invoice() {
		return frappe.run_serially([
			() => this.make_sales_invoice_frm(),
			() => this.set_pos_profile_data(),
			() => this.set_invoice_status(),
			() => this.cart.fetch_customer_details(this.frm.doc.customer),
			() => this.cart.update_customer_section(this.frm),
			() => this.cart.update_totals_section(this.frm)
		]);
	}

	make_sales_invoice_frm() {
		const doctype = 'POS Invoice';
		return new Promise(resolve => {
			if (this.frm) {
				this.frm = this.get_new_frm(this.frm);
				this.frm.doc.items = [];
				this.frm.doc.is_pos = 1
				resolve();
			} else {
				frappe.model.with_doctype(doctype, () => {
					this.frm = this.get_new_frm();
					this.frm.doc.items = [];
					this.frm.doc.is_pos = 1
					resolve();
				});
			}
		});
	}

	get_new_frm(_frm) {
		const doctype = 'POS Invoice';
		const page = $('<div>');
		const frm = _frm || new frappe.ui.form.Form(doctype, page, false);
		const name = frappe.model.make_new_doc_and_get_name(doctype, true);
		frm.refresh(name);

		return frm;
	}

	async make_return_invoice(doc) {
		this.frm = this.get_new_frm(this.frm);
		this.frm.doc.items = [];
		const res = await frappe.call({
			method: "erpnext.selling.doctype.pos_invoice.pos_invoice.make_sales_return",
			args: {
				'source_name': doc.name,
				'target_doc': this.frm.doc
			}
		});
		frappe.model.sync(res.message);
		await this.set_pos_profile_data();
	}

	set_pos_profile_data() {
		if (this.company && !this.frm.doc.company) this.frm.doc.company = this.company;
		if (this.pos_profile && !this.frm.doc.pos_profile) this.frm.doc.pos_profile = this.pos_profile;
		if (!this.frm.doc.company) return;

		return new Promise(resolve => {
			return this.frm.call({
				doc: this.frm.doc,
				method: "set_missing_values",
			}).then((r) => {
				if(!r.exc) {
					if (!this.frm.doc.pos_profile) {
						frappe.dom.unfreeze();
						this.raise_exception_for_pos_profile();
					}
					this.frm.trigger("update_stock");
					this.frm.trigger('calculate_taxes_and_totals');
					if(this.frm.doc.taxes_and_charges) me.frm.script_manager.trigger("taxes_and_charges");
					frappe.model.set_default_values(this.frm.doc);
					if (r.message) {
						this.frm.pos_print_format = r.message.print_format || "";
						this.frm.meta.default_print_format = r.message.print_format || "";
						this.frm.allow_edit_rate = r.message.allow_edit_rate;
						this.frm.allow_edit_discount = r.message.allow_edit_discount;
						this.frm.doc.campaign = r.message.campaign;
						this.frm.allow_print_before_pay = r.message.allow_print_before_pay;
					}
				}
				resolve();
			});
		});
	}

	raise_exception_for_pos_profile() {
		setTimeout(() => frappe.set_route('List', 'POS Profile'), 2000);
		frappe.throw(__("POS Profile is required to use Point-of-Sale"));
	}

	set_invoice_status() {
		const [status, indicator] = frappe.listview_settings["POS Invoice"].get_indicator(this.frm.doc);
		this.page.set_indicator(__(`${status}`), indicator);
	}

	async on_cart_update(args) {
		frappe.dom.freeze();
		try {
			let { field, value, item } = args;
			const { item_code, batch_no } = item;
			let item_row = this.get_item_from_frm(item_code, batch_no);

			if (item_row) {
				field === 'qty' && (value = flt(value));

				if (field === 'qty' && value > 0) await this.check_stock_availability(item_row, this.frm.doc.set_warehouse);
				
				if (this.is_current_item_being_edited(item_row)) {
					await frappe.model.set_value(item_row.doctype, item_row.name, field, value);
					this.update_cart_html(item_row);
					frappe.dom.unfreeze()
				}

			} else {
				if (!this.frm.doc.customer) {
					frappe.dom.unfreeze();
					frappe.show_alert({
						message: __('You must select a customer before adding an item.'),
						indicator: 'orange'
					})
					return;
				}

				const args = { item_code: item_code, batch_no, [field]: value };
				if (field === 'serial_no') args['qty'] = value.split(`\n`).length || 0;

				item_row = this.frm.add_child('items', args);

				if (field === 'qty' && value !== 0) await this.check_stock_availability(item_row, this.frm.doc.set_warehouse);

				await this.trigger_new_item_events(item_row);

				this.show_serial_batch_selector(item_row),
				this.update_cart_html(item_row),
				frappe.dom.unfreeze()
			}	
		} catch (error) {
			console.log(error);
			frappe.dom.unfreeze();
		}
	}

	get_item_from_frm(item_code, batch_no) {
		return this.frm.doc.items.find(i => i.item_code === item_code && i.batch_no == batch_no);
	}

	is_current_item_being_edited(item_row) {
		const { item_code, batch_no } = this.item_details.current_item;

		return item_code !== item_row.item_code || batch_no != item_row.batch_no ? false : true;
	}

	update_cart_html(item_row, remove_item) {
		this.cart.update_item_html(item_row, remove_item);
		this.cart.update_totals_section(this.frm);
	}

	check_dialog_condition(item_row) {
		const serialized = item_row.has_serial_no;
		const batched = item_row.has_batch_no;
		const no_serial_selected = item_row.has_serial_no && !item_row.serial_no;
		const no_batch_selected = item_row.has_batch_no && !item_row.batch_no;

		// TODO : 
		// if actual_batch_qty and actual_qty is same then there's only one batch. So no point showing the dialog

		if ((serialized && no_serial_selected) || (batched && no_batch_selected) || 
			(serialized && batched && (no_batch_selected || no_serial_selected))) {
			return true;
		}
		return false;
	}

	show_serial_batch_selector(item_row) {
		this.item_details.toggle_item_details_section(item_row);
	}

	async trigger_new_item_events(item_row) {
		await this.frm.script_manager.trigger('item_code', item_row.doctype, item_row.name)
		await this.frm.script_manager.trigger('qty', item_row.doctype, item_row.name)
	}

	async check_stock_availability(item_row, warehouse) {
		const res = await frappe.call({
			method: "erpnext.selling.doctype.pos_invoice.pos_invoice.get_stock_availability",
			args: {
				'item_code': item_row.item_code,
				'warehouse': warehouse,
			}
		})
		frappe.dom.unfreeze();
		if (!(res.message > 0)) {
			frappe.model.clear_doc(item_row.doctype, item_row.name);
			frappe.throw(frappe._(`Item Code: ${item_row.item_code.bold()} is not available under warehouse ${warehouse.bold()}.`))
		} else if (res.message < item_row.qty) {
			frappe.msgprint(frappe._(`Stock quantity not enough for Item Code: ${item_row.item_code.bold()} under warehouse ${warehouse.bold()}. 
				Available quantity ${res.message.toString().bold()}.`))
			this.item_details.qty_control.set_value(res.message);
			return res.message;
		}
		frappe.dom.freeze();
		return item_row.qty;
	}

	toggle_item_details(item_code, batch_no) {
		const item_row = this.frm.doc.items.find(i => i.item_code === item_code && (!batch_no || (batch_no && i.batch_no === batch_no)));
		this.item_details.toggle_item_details_section(item_row || undefined);
	}

	update_item_field(value, field_or_action) {
		if (field_or_action === 'done') {
			this.toggle_item_details();
		} else if (field_or_action === 'remove') {
			this.remove_item_from_cart();
		} else {
			const field_control = this.item_details[`${field_or_action}_control`];
			if (!field_control) return;
			value != "" && field_control.set_value(value);
		}
	}

	remove_item_from_cart() {
		frappe.dom.freeze();
		const { doctype, name, current_item } = this.item_details;

		frappe.model.set_value(doctype, name, 'qty', 0);

		this.frm.script_manager.trigger('qty', doctype, name).then(() => {
			frappe.model.clear_doc(doctype, name);
			this.update_cart_html(current_item, true);
			this.toggle_item_details();
			frappe.dom.unfreeze();
		})
	}
}

