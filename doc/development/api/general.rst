.. highlight:: python
   :linenothreshold: 5

General APIs
============

This page lists some general signals and hooks which do not belong to a
specific type of plugin but might come in handy for various plugins.

Core
----

.. automodule:: pretix.base.signals
   :members: periodic_task, event_live_issues, event_copy_data, email_filter, register_notification_types, notification,
      item_copy_data, register_sales_channel_types, register_global_settings, quota_availability, global_email_filter,
      register_ticket_secret_generators, gift_card_transaction_display,
      register_text_placeholders, register_mail_placeholders, device_info_updated

Order events
""""""""""""

There are multiple signals that will be sent out in the ordering cycle:

.. automodule:: pretix.base.signals
   :no-index:
   :members: validate_cart, validate_cart_addons, validate_order, order_valid_if_pending, order_fee_calculation, order_paid, order_placed, order_canceled, order_reactivated, order_expired, order_expiry_changed, order_modified, order_changed, order_approved, order_denied, order_fee_type_name, allow_ticket_download, order_split, order_gracefully_delete, invoice_line_text

Check-ins
"""""""""

.. automodule:: pretix.base.signals
   :no-index:
   :members: checkin_created


Frontend
--------

.. automodule:: pretix.presale.signals
   :members: html_head, html_footer, footer_link, global_footer_link, front_page_top, front_page_bottom, front_page_bottom_widget, fee_calculation_for_cart, contact_form_fields, question_form_fields, contact_form_fields_overrides, question_form_fields_overrides, checkout_confirm_messages, checkout_confirm_page_content, checkout_all_optional, html_page_header, render_seating_plan, checkout_flow_steps, position_info, position_info_top, item_description, global_html_head, global_html_footer, global_html_page_header, seatingframe_html_head


.. automodule:: pretix.presale.signals
   :no-index:
   :members: order_info, order_info_top, order_meta_from_request, order_api_meta_from_request

Request flow
""""""""""""

.. automodule:: pretix.presale.signals
   :no-index:
   :members: process_request, process_response

Vouchers
""""""""

.. automodule:: pretix.presale.signals
   :no-index:
   :members: voucher_redeem_info

Backend
-------

.. automodule:: pretix.control.signals
   :members: nav_event, html_head, html_page_start, quota_detail_html, nav_topbar, nav_global, nav_organizer, nav_event_settings,
             order_info, event_settings_widget, oauth_application_registered, order_position_buttons, subevent_forms,
             item_formsets, order_search_filter_q, order_search_forms

.. automodule:: pretix.base.signals
   :no-index:
   :members: logentry_display, logentry_object_link, requiredaction_display, timeline_events, orderposition_blocked_display, customer_created, customer_signed_in

Vouchers
""""""""

.. automodule:: pretix.control.signals
   :no-index:
   :members: item_forms, voucher_form_class, voucher_form_html, voucher_form_validation

Dashboards
""""""""""

.. automodule:: pretix.control.signals
   :no-index:
   :members: event_dashboard_widgets, user_dashboard_widgets, event_dashboard_top

Ticket designs
""""""""""""""

.. automodule:: pretix.base.signals
   :no-index:
   :members: layout_text_variables, layout_image_variables

.. automodule:: pretix.plugins.ticketoutputpdf.signals
   :members: override_layout

API
---

.. automodule:: pretix.base.signals
   :no-index:
   :members: validate_event_settings, api_event_settings_fields

.. automodule:: pretix.api.signals
   :no-index:
   :members: register_device_security_profile, order_api_details, orderposition_api_details
