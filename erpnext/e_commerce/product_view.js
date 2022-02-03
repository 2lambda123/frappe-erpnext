erpnext.ProductView =  class {
	/* Options:
		- View Type
		- Products Section Wrapper,
		- Item Group: If its an Item Group page
	*/
	constructor(options) {
		Object.assign(this, options);
		this.preference = this.view_type;
		this.make();
	}

	make() {
		this.products_section.empty();
		this.prepare_view_toggler();
		this.get_item_filter_data();
	}

	prepare_view_toggler() {
		if (!$("#list").length || !$("#image-view").length) {
			this.render_view_toggler();
			this.bind_view_toggler_actions();
			this.set_view_state();
		}
	}

	get_item_filter_data() {
		// Get and render all Product related views
		let me = this;
		let args = this.get_query_filters();

		this.disable_view_toggler(true);

		frappe.call({
			method: 'erpnext.e_commerce.doctype.website_item.website_item.get_product_filter_data',
			args: args,
			callback: function(result) {
				if (!result.exc && result && result.message) {
					if (me.item_group && result.message[3].length) {
						me.render_item_sub_categories(result.message[3]);
					}

					if (!result.message[0].length) {
						// if result has no items or result is empty
						me.render_no_products_section();
					} else {
						me.render_filters(result.message[1]);

						// Render views
						me.render_list_view(result.message[0], result.message[2]);
						me.render_grid_view(result.message[0], result.message[2]);
						me.products = result.message[0];
					}

					// Bottom paging
					me.add_paging_section(result.message[2]);
				} else {
					me.render_no_products_section();
				}

				me.disable_view_toggler(false);
			}
		});
	}

	disable_view_toggler(disable=false) {
		$('#list').prop('disabled', disable);
		$('#image-view').prop('disabled', disable);
	}

	render_filters(filter_data) {
		this.get_discount_filter_html(filter_data.discount_filters);
		this.bind_filters();
		this.restore_filters_state();
	}

	render_grid_view(items, settings) {
		// loop over data and add grid html to it
		let me = this;
		this.prepare_product_area_wrapper("grid");

		frappe.require('/assets/js/e-commerce.min.js', function() {
			new erpnext.ProductGrid({
				items: items,
				products_section: $("#products-grid-area"),
				settings: settings,
				preference: me.preference
			});
		});
	}

	render_list_view(items, settings) {
		let me = this;
		this.prepare_product_area_wrapper("list");

		frappe.require('/assets/js/e-commerce.min.js', function() {
			new erpnext.ProductList({
				items: items,
				products_section: $("#products-list-area"),
				settings: settings,
				preference: me.preference
			});
		});
	}

	prepare_product_area_wrapper(view) {
		let left_margin = view == "list" ? "ml-2" : "";
		let top_margin = view == "list" ? "mt-8" : "mt-4";
		return this.products_section.append(`
			<br>
			<div id="products-${view}-area" class="row products-list ${ top_margin } ${ left_margin }"></div>
		`);
	}

	get_query_filters() {
		const filters = frappe.utils.get_query_params();
		let {field_filters, attribute_filters} = filters;

		field_filters = field_filters ? JSON.parse(field_filters) : {};
		attribute_filters = attribute_filters ? JSON.parse(attribute_filters) : {};

		return {
			field_filters: field_filters,
			attribute_filters: attribute_filters,
			item_group: this.item_group,
			start: filters.start || null
		};
	}

	add_paging_section(settings) {
		$(".product-paging-area").remove();

		if (this.products) {
			let paging_html = `
				<div class="row product-paging-area mt-5">
					<div class="col-3">
					</div>
					<div class="col-9 text-right">
			`;
			let query_params = frappe.utils.get_query_params();
			let start = query_params.start ? cint(JSON.parse(query_params.start)) : 0;
			let page_length = settings.products_per_page || 0;

			if (start > 0) {
				paging_html += `
					<button class="btn btn-default btn-prev" data-start="${ start - page_length }" style="float: left">
						${ __("Prev") }
					</button>`;
			}
			if (this.products.length > page_length || this.products.length == page_length) {
				paging_html += `
					<button class="btn btn-default btn-next" data-start="${ start + page_length }">
						${ __("Next") }
					</button>
				`;
			}
			paging_html += `</div></div>`;

			$(".page_content").append(paging_html);
			this.bind_paging_action();
		}
	}

	render_view_toggler() {
		["btn-list-view", "btn-grid-view"].forEach(view => {
			let icon = view === "btn-list-view" ? "list" : "image-view";
			this.products_section.append(`
			<div class="form-group mb-0" id="toggle-view">
				<button id="${ icon }" class="btn ${ view } mr-2">
					<span>
						<svg class="icon icon-md">
							<use href="#icon-${ icon }"></use>
						</svg>
					</span>
				</button>
			</div>`);
		});
	}

	bind_view_toggler_actions() {
		$("#list").click(function() {
			let $btn = $(this);
			$btn.removeClass('btn-primary');
			$btn.addClass('btn-primary');
			$(".btn-grid-view").removeClass('btn-primary');

			$("#products-grid-area").addClass("hidden");
			$("#products-list-area").removeClass("hidden");
		});

		$("#image-view").click(function() {
			let $btn = $(this);
			$btn.removeClass('btn-primary');
			$btn.addClass('btn-primary');
			$(".btn-list-view").removeClass('btn-primary');

			$("#products-list-area").addClass("hidden");
			$("#products-grid-area").removeClass("hidden");
		});
	}

	set_view_state() {
		if (this.preference === "List View") {
			$("#list").addClass('btn-primary');
			$("#image-view").removeClass('btn-primary');
		} else {
			$("#image-view").addClass('btn-primary');
			$("#list").removeClass('btn-primary');
		}
	}

	bind_paging_action() {
		$('.btn-prev, .btn-next').click((e) => {
			const $btn = $(e.target);
			$btn.prop('disabled', true);
			const start = $btn.data('start');
			let query_params = frappe.utils.get_query_params();
			query_params.start = start;
			let path = window.location.pathname + '?' + frappe.utils.get_url_from_dict(query_params);
			window.location.href = path;
		});
	}

	get_discount_filter_html(filter_data) {
		$("#discount-filters").remove();
		if (filter_data) {
			$("#product-filters").append(`
				<div id="discount-filters" class="mb-4 filter-block pb-5">
					<div class="filter-label mb-3">${ __("Discounts") }</div>
				</div>
			`);

			let html = `<div class="filter-options">`;
			filter_data.forEach(filter => {
				html += `
					<div class="checkbox">
						<label data-value="${ filter[0] }">
							<input type="radio"
								class="product-filter discount-filter"
								name="discount" id="${ filter[0] }"
								data-filter-name="discount"
								data-filter-value="${ filter[0] }"
							>
								<span class="label-area" for="${ filter[0] }">
									${ filter[1] }
								</span>
						</label>
					</div>
				`;
			});
			html += `</div>`;

			$("#discount-filters").append(html);
		}
	}

	bind_filters() {
		let me = this;
		this.field_filters = {};
		this.attribute_filters = {};

		$('.product-filter').on('change', (e) => {
			const $checkbox = $(e.target);
			const is_checked = $checkbox.is(':checked');

			if ($checkbox.is('.attribute-filter')) {
				const {
					attributeName: attribute_name,
					attributeValue: attribute_value
				} = $checkbox.data();

				if (is_checked) {
					this.attribute_filters[attribute_name] = this.attribute_filters[attribute_name] || [];
					this.attribute_filters[attribute_name].push(attribute_value);
				} else {
					this.attribute_filters[attribute_name] = this.attribute_filters[attribute_name] || [];
					this.attribute_filters[attribute_name] = this.attribute_filters[attribute_name].filter(v => v !== attribute_value);
				}

				if (this.attribute_filters[attribute_name].length === 0) {
					delete this.attribute_filters[attribute_name];
				}
			} else if ($checkbox.is('.field-filter') || $checkbox.is('.discount-filter')) {
				const {
					filterName: filter_name,
					filterValue: filter_value
				} = $checkbox.data();

				if ($checkbox.is('.discount-filter')) {
					// clear previous discount filter to accomodate new
					delete this.field_filters["discount"];
				}
				if (is_checked) {
					this.field_filters[filter_name] = this.field_filters[filter_name] || [];
					this.field_filters[filter_name].push(filter_value);
				} else {
					this.field_filters[filter_name] = this.field_filters[filter_name] || [];
					this.field_filters[filter_name] = this.field_filters[filter_name].filter(v => v !== filter_value);
				}

				if (this.field_filters[filter_name].length === 0) {
					delete this.field_filters[filter_name];
				}
			}

			let route_params = frappe.utils.get_query_params();
			const query_string = me.get_query_string({
				start: me.if_key_exists(route_params.start) || 0,
				field_filters: JSON.stringify(me.if_key_exists(this.field_filters)),
				attribute_filters: JSON.stringify(me.if_key_exists(this.attribute_filters)),
			});
			window.history.pushState('filters', '', `${location.pathname}?` + query_string);

			$('.page_content input').prop('disabled', true);
			me.make();
			$('.page_content input').prop('disabled', false);
		});
	}

	restore_filters_state() {
		const filters = frappe.utils.get_query_params();
		let {field_filters, attribute_filters} = filters;

		if (field_filters) {
			field_filters = JSON.parse(field_filters);
			for (let fieldname in field_filters) {
				const values = field_filters[fieldname];
				const selector = values.map(value => {
					return `input[data-filter-name="${fieldname}"][data-filter-value="${value}"]`;
				}).join(',');
				$(selector).prop('checked', true);
			}
			this.field_filters = field_filters;
		}
		if (attribute_filters) {
			attribute_filters = JSON.parse(attribute_filters);
			for (let attribute in attribute_filters) {
				const values = attribute_filters[attribute];
				const selector = values.map(value => {
					return `input[data-attribute-name="${attribute}"][data-attribute-value="${value}"]`;
				}).join(',');
				$(selector).prop('checked', true);
			}
			this.attribute_filters = attribute_filters;
		}
	}

	render_no_products_section() {
		this.products_section.append(`
			<br><br><br>
			<div class="cart-empty frappe-card">
				<div class="cart-empty-state">
					<img src="/assets/erpnext/images/ui-states/cart-empty-state.png" alt="Empty Cart">
				</div>
				<div class="cart-empty-message mt-4">${ __('No products found') }</p>
			</div>
		`);
	}

	render_item_sub_categories(categories) {
		if (categories && categories.length) {
			let sub_group_html = `
				<div class="sub-category-container">
					<div class="heading"> ${ __('Sub Categories') } </div>
				</div>
				<div class="sub-category-container scroll-categories">
			`;

			categories.forEach(category => {
				sub_group_html += `
					<a href="${ category.route || '#' }" style="text-decoration: none;">
						<div class="category-pill">
							${ category.name }
						</div>
					</a>
				`;
			});
			sub_group_html += `</div>`;

			$("#product-listing").prepend(sub_group_html);
		}
	}

	get_query_string(object) {
		const url = new URLSearchParams();
		for (let key in object) {
			const value = object[key];
			if (value) {
				url.append(key, value);
			}
		}
		return url.toString();
	}

	if_key_exists(obj) {
		let exists = false;
		for (let key in obj) {
			if (obj.hasOwnProperty(key) && obj[key]) {
				exists = true;
				break;
			}
		}
		return exists ? obj : undefined;
	}
}