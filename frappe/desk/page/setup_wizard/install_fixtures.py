# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import N_
from frappe.deprecation_dumpster import _
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards


def install():
	update_genders()
	update_salutations()
	update_global_search_doctypes()
	sync_dashboards()
	add_unsubscribe()


def update_genders():
	for gender in (
		N_("Male"),
		N_("Female"),
		N_("Other"),
		N_("Transgender"),
		N_("Genderqueer"),
		N_("Non-Conforming"),
		N_("Prefer not to say"),
	):
		doc = frappe.new_doc("Gender")
		doc.gender = gender
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def update_salutations():
	for salutation in (
		N_("Mr"),
		N_("Ms"),
		N_("Mx"),
		N_("Dr"),
		N_("Mrs"),
		N_("Madam"),
		N_("Miss"),
		N_("Master"),
		N_("Prof"),
	):
		doc = frappe.new_doc("Salutation")
		doc.salutation = salutation
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def add_unsubscribe():
	"""Seed the Guest account into the global unsubscribe list.

	Administrator is deliberately NOT added here: Administrator is a real
	account that must be able to receive system mail (e.g. 2FA/OTP
	verification codes). Unconditionally unsubscribing it -- as this used
	to do for the "admin@example.com" placeholder address -- silently
	swallows every email addressed to Administrator, including
	verification mail, with no UI indication that this is happening.
	"""
	administrator_email = frappe.db.get_value("User", "Administrator", "email")
	guest_email = frappe.db.get_value("User", "Guest", "email")

	# Defensive cleanup: if an Email Unsubscribe row already exists for
	# Administrator's current email (e.g. left over from a fixture re-run
	# or an old site), remove it so Administrator can still be mailed.
	if administrator_email:
		frappe.db.delete(
			"Email Unsubscribe", {"email": administrator_email, "global_unsubscribe": 1}
		)

	if guest_email and not frappe.get_all(
		"Email Unsubscribe", filters={"email": guest_email, "global_unsubscribe": 1}
	):
		doc = frappe.new_doc("Email Unsubscribe")
		doc.update({"email": guest_email, "global_unsubscribe": 1})
		doc.insert(ignore_permissions=True)
