{% include "erpnext/selling/page/point_of_sale_beta/pos_number_pad.js" %}

erpnext.PointOfSale.Payment = class {
	constructor({ events, wrapper }) {
		this.wrapper = wrapper;
		this.events = events;

		this.initialize_app();
	}

	initialize_app() {
        this.prepare_dom();
        this.initialize_numpad();
        this.bind_events();
	}

	prepare_dom() {
		this.wrapper.append(
            `<section class="col-span-6 flex shadow rounded payment-section bg-white mx-h-70 h-100 d-none">
                <div class="flex flex-col p-16 pt-8 pb-8 w-full">
                    <div class="text-grey mb-6">PAYMENT METHOD</div>
                    <div class="payment-modes flex flex-wrap"></div>
                    <div class="flex mt-auto justify-center w-full">
                        <div class="flex flex-col justify-center flex-1 ml-4">
                            <div class="flex w-full mb-4">
                                <div class="totals-remarks items-end justify-end flex flex-1">
                                    <div class="remarks mr-4 text-md text-grey mr-auto">+ Add Remark</div>
                                    <div class="totals flex justify-end pt-4"></div>
                                </div>
                                <div class="number-pad w-40 mb-4 ml-8 d-none"></div>
                            </div>
                            <div class="flex items-center justify-center submit-order h-16 w-full rounded bg-primary text-md text-white no-select pointer text-bold">
                                Complete Order
                            </div>
                        </div>
                    </div>
                </div>
            </section>`
        )
        this.$component = this.wrapper.find('.payment-section');
		this.$payment_modes = this.$component.find('.payment-modes');
		this.$totals_remarks = this.$component.find('.totals-remarks');
		this.$totals = this.$component.find('.totals');
		this.$remarks = this.$component.find('.remarks');
		this.$numpad = this.$component.find('.number-pad');
	}

	initialize_numpad() {
		const me = this;
		this.number_pad = new erpnext.PointOfSale.NumberPad({
			wrapper: this.$numpad,
			events: {
				numpad_event: function($btn) {
					me.on_numpad_clicked($btn);
				}
			},
			cols: 3,
			keys: [
				[ 1, 2, 3 ],
				[ 4, 5, 6 ],
				[ 7, 8, 9 ],
				[ '.', 0, 'Delete' ]
			],
		})

		this.numpad_value = '';
	}

	on_numpad_clicked($btn) {
		const me = this;
		const button_value = $btn.attr('data-button-value');

		highlight_numpad_btn($btn);
		this.numpad_value = button_value === 'delete' ? this.numpad_value.slice(0, -1) : this.numpad_value + button_value;
		this.selected_mode.$input.get(0).focus();
		this.selected_mode.set_value(this.numpad_value);

		function highlight_numpad_btn($btn) {
			$btn.addClass('shadow-inner bg-selected');
			setTimeout(() => {
				$btn.removeClass('shadow-inner bg-selected');
			}, 100);
		}
	}

	bind_events() {
		const me = this;

		this.$payment_modes.on('click', '.mode-of-payment', function(e) {
			const clicked_mode = $(this);
			if (!$(e.target).is(clicked_mode)) return;

			const mode = clicked_mode.attr('data-mode');

			// reset and hide all control fields
			$(`.mode-of-payment-control`).addClass('d-none');
			$(`.shortcuts`).addClass('d-none');
			me.$payment_modes.find(`.${mode}-amount`).removeClass('d-none');
			me.$payment_modes.find(`.loyalty-program-name`).addClass('d-none');

			// remove highlight from all mode-of-payments except the clicked one
			$('.mode-of-payment').not(this).removeClass('border-primary');

			if (clicked_mode.hasClass('border-primary')) {
				// clicked one is selected then unselect it
				clicked_mode.removeClass('border-primary');
				clicked_mode.find('.mode-of-payment-control').addClass('d-none');
				clicked_mode.find('.shortcuts').addClass('d-none');
				me.$payment_modes.find(`.${mode}-amount`).removeClass('d-none');
				me.$payment_modes.find(`.loyalty-program-name`).addClass('d-none');
				me.selected_mode = '';
				me.toggle_numpad(false);
			} else {
				// clicked one is not selected then select it
				clicked_mode.addClass('border-primary');
				clicked_mode.find('.mode-of-payment-control').removeClass('d-none');
				clicked_mode.find('.shortcuts').removeClass('d-none');
				me.$payment_modes.find(`.${mode}-amount`).addClass('d-none');
				me.$payment_modes.find(`.loyalty-program-name`).removeClass('d-none');
				me.toggle_numpad(true);
				me.selected_mode = me[`${mode}_control`];
				me.selected_mode?.$input.get(0).focus();
			}
		})

		this.$payment_modes.on('click', '.shortcut', function(e) {
			const value = $(this).attr('data-value');
			me.selected_mode.set_value(value);
		})

		this.$totals_remarks.on('click', '.remarks', () => {
			this.toggle_remarks_control();
		})

		this.$component.on('click', '.submit-order', () => {
			this.events.submit_invoice();
		})

		frappe.ui.form.on('POS Invoice', 'paid_amount', (frm, cdt, cdn) => {
			this.show_totals(frm.doc);
		})

		frappe.ui.form.on('POS Invoice', 'loyalty_amount', (frm) => {
			const formatted_currency = format_currency(frm.doc.loyalty_amount, frm.doc.currency);
			this.$payment_modes.find(`.loyalty-points-amount`).html(formatted_currency);
		})
	}

	toggle_numpad(show) {
		if (show) {
			this.$numpad.removeClass('d-none');
			this.$remarks.addClass('d-none');
			this.$totals_remarks.addClass('w-60 justify-center').removeClass('justify-end w-full');
		} else {
			this.$numpad.addClass('d-none');
			this.$remarks.removeClass('d-none');
			this.$totals_remarks.removeClass('w-60 justify-center').addClass('justify-end w-full');
		}
	}

	render_payment_section() {
		this.show_payment_section();
		this.render_payment_mode_dom();
		this.show_totals();
	}

	hide_payment_section() {
		this.events.toggle_other_sections(false);
		this.$component.addClass('d-none');
	}

	show_payment_section() {
		this.events.toggle_other_sections(true);
		this.$component.removeClass('d-none');
	}

	toggle_remarks_control() {
		if (this.$remarks.find('.frappe-control').length) {
			this.$remarks.html('+ Add Remark');
		} else {
			this.$remarks.html('');
			this[`remark_control`] = frappe.ui.form.make_control({
				df: {
					label: 'Remark',
					fieldtype: 'Text',
					onchange: function() {
						// frappe.model.set_value(p.doctype, p.name, 'amount', flt(this.value)).then(() => me.show_totals());
						// me.$payment_modes.find(`.${mode}-amount`).html(`${format_currency(this.value, currency)}`);
					}
				},
				parent: this.$totals_remarks.find(`.remarks`),
				render_input: true,
			});
			this[`remark_control`].set_value('');
		}
	}

	render_payment_mode_dom() {
		const doc = this.events.get_frm().doc;
		const payments = doc.payments;
		const grand_total = doc.grand_total;
		const currency = doc.currency;

		this.$payment_modes.html(
		   `${
			   payments.map((p, i) => {
				const mode = p.mode_of_payment.replace(' ', '_').toLowerCase();
				const payment_type = p.type;
				const margin = i % 2 === 0 ? 'pr-2' : 'pl-2';
				const amount = p.amount > 0 ? format_currency(p.amount, currency) : '';

				return (
					`<div class="w-half ${margin}">
						<div class="mode-of-payment rounded border border-grey text-grey text-md
								mb-4 p-8 pt-4 pb-4 no-select pointer" data-mode="${mode}" data-payment-type="${payment_type}">
							${p.mode_of_payment}
							<div class="${mode}-amount inline float-right text-bold">${amount}</div>
							<div class="${mode} mode-of-payment-control mt-4 flex flex-1 items-center d-none"></div>
						</div>
					</div>`
				)
			   }).join('')
		   }`
		)

		payments.forEach(p => {
			const mode = p.mode_of_payment.replace(' ', '_').toLowerCase();
			const me = this;
			this[`${mode}_control`] = frappe.ui.form.make_control({
				df: {
					label: __(`${p.mode_of_payment}`),
					fieldtype: 'Currency',
					placeholder: __(`Enter ${p.mode_of_payment} amount.`),
					onchange: function() {
						frappe.model.set_value(p.doctype, p.name, 'amount', flt(this.value))
							.then(() => me.show_totals());

						const formatted_currency = format_currency(this.value, currency);
						me.$payment_modes.find(`.${mode}-amount`).html(formatted_currency);
					}
				},
				parent: this.$payment_modes.find(`.${mode}.mode-of-payment-control`),
				render_input: true,
			});
			this[`${mode}_control`].toggle_label(false);
			this[`${mode}_control`].set_value(p.amount);
		})

		this.render_loyalty_points_payment_mode();

		const nearest_10 = Math.ceil((grand_total / 10)) * 10;
		const nearest_50 = Math.ceil((grand_total / 50)) * 50;
		const nearest_100 = Math.ceil((grand_total / 100)) * 100;

		const shortcuts = [nearest_10, nearest_50, nearest_100];

		this.$payment_modes.find('[data-payment-type="Cash"]').find('.mode-of-payment-control').after(
			`<div class="shortcuts grid grid-cols-3 gap-2 flex-1 text-center text-md-0 mb-2 d-none">
				${
					shortcuts.map(s => {
						return `<div class="shortcut rounded bg-light-grey text-dark-grey pt-2 pb-2 no-select pointer" data-value="${s}">
									${format_currency(s, currency)}
								</div>`
					}).join('')
				}
			</div>`
		)
	}

	render_loyalty_points_payment_mode() {
		const doc = this.events.get_frm().doc;
		const me = this;

		frappe.db.get_value('Customer', doc.customer, 'loyalty_program', ({ loyalty_program }) => {
			if (!loyalty_program) {
				return this.render_add_payment_method_dom();
			}

			const lp_details_promise = this.get_loyalty_program_details(doc.customer, loyalty_program, doc.posting_date, doc.company);

			lp_details_promise.then(({ message: details }) => {
				let description, read_only;
				if (!details.loyalty_points) {
					description = __(`You don't have enough points to redeem.`);
					read_only = true;
				} else {
					description = __(`You can redeem upto ${details.loyalty_points} points.`);
					read_only = false;
				}

				const margin = this.$payment_modes.children().length % 2 === 0 ? 'pr-2' : 'pl-2';
				const amount = doc.loyalty_amount > 0 ? format_currency(doc.loyalty_amount, doc.currency) : '';
				this.$payment_modes.append(
					`<div class="w-half ${margin}">
						<div class="mode-of-payment rounded border border-grey text-grey text-md
								mb-4 p-8 pt-4 pb-4 no-select pointer" data-mode="loyalty-points" data-payment-type="loyalty-points">
							Loyalty Points
							<div class="loyalty-points-amount inline float-right text-bold">${amount}</div>
							<div class="loyalty-program-name inline float-right text-bold text-md-0 d-none">${loyalty_program}</div>
							<div class="loyalty-points mode-of-payment-control mt-4 flex flex-1 items-center d-none"></div>
						</div>
					</div>`
				)

				this.loyalty_points_control = frappe.ui.form.make_control({
					df: {
						label: __('Loyalty Points'),
						fieldtype: 'Int',
						placeholder: __(`Enter loyalty points to be redeemed.`),
						read_only,
						onchange: async function() {
							const redeem_loyalty_points = this.value > 0 ? 1 : 0;
							await frappe.model.set_value(doc.doctype, doc.name, 'redeem_loyalty_points', redeem_loyalty_points);

							frappe.model.set_value(doc.doctype, doc.name, 'loyalty_points', flt(this.value));
						},
						description
					},
					parent: this.$payment_modes.find(`.loyalty-points.mode-of-payment-control`),
					render_input: true,
				});
				this.loyalty_points_control.toggle_label(false);

				this.render_add_payment_method_dom();
			})
		});
	}

	get_loyalty_program_details(customer, loyalty_program, posting_date, company) {
		return frappe.call({
			method: "erpnext.accounts.doctype.loyalty_program.loyalty_program.get_loyalty_program_details_with_points",
			args: { customer, loyalty_program, posting_date, company, "silent": true },
		});
	}

	render_add_payment_method_dom() {
		this.$payment_modes.append(
			`<div class="w-full pr-2">
				<div class="add-mode-of-payment w-half text-grey mb-4 no-select pointer">+ Add Payment Method</div>
			</div>`
		)
	}

	show_totals(doc) {
		if (!doc) doc = this.events.get_frm().doc;
		const paid_amount = doc.paid_amount;
		const remaining = doc.grand_total - doc.paid_amount;
		const change = doc.change_amount;
		const currency = doc.currency
		const label = change ? __('Change') : __('To Be Paid');

		this.$totals.html(
			`<div>
				<div class="pr-8 border-r-grey">Paid Amount</div>
				<div class="pr-8 border-r-grey text-bold text-2xl">${format_currency(paid_amount, currency)}</div>
			</div>
			<div>
				<div class="pl-8">${label}</div>
				<div class="pl-8 text-green-400 text-bold text-2xl">${format_currency(change || remaining, currency)}</div>
			</div>`
		)
	}
 }