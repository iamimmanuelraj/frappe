# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Regression tests for the Administrator/Guest placeholder-email lockout.

Context: Administrator and Guest historically shipped with their email
hardcoded to admin@example.com / guest@example.com, and both addresses were
unconditionally added to the Email Unsubscribe list on install. Since
example.com never resolves and the address is unsubscribed, mail addressed
to Administrator (2FA/OTP verification in particular) was always silently
swallowed with no way for the operator to find out -- a dead-end lockout on
any site that never customised the default.
"""

import importlib

import frappe
from frappe.desk.page.setup_wizard.install_fixtures import add_unsubscribe
from frappe.tests import IntegrationTestCase


class TestAdminGuestEmailDeliverability(IntegrationTestCase):
	def setUp(self):
		self._admin_email = frappe.db.get_value("User", "Administrator", "email")
		self._guest_email = frappe.db.get_value("User", "Guest", "email")

	def tearDown(self):
		frappe.db.set_value("User", "Administrator", "email", self._admin_email, update_modified=False)
		frappe.db.set_value("User", "Guest", "email", self._guest_email, update_modified=False)
		frappe.db.delete("Email Unsubscribe", {"email": ("in", ["admin@example.com", self._admin_email])})
		frappe.db.commit()

	def test_add_unsubscribe_never_unsubscribes_administrator(self):
		"""add_unsubscribe() must not add Administrator's email to the global
		unsubscribe list, and must clear any pre-existing entry for it, else
		Administrator can never receive system mail (2FA OTPs included)."""
		frappe.db.set_value("User", "Administrator", "email", "admin@example.com", update_modified=False)

		# Simulate a stale/pre-existing unsubscribe row for Administrator
		# (this is exactly what every default install used to create).
		if not frappe.db.exists("Email Unsubscribe", {"email": "admin@example.com"}):
			frappe.get_doc(
				{"doctype": "Email Unsubscribe", "email": "admin@example.com", "global_unsubscribe": 1}
			).insert(ignore_permissions=True)

		add_unsubscribe()

		self.assertFalse(
			frappe.db.exists(
				"Email Unsubscribe", {"email": "admin@example.com", "global_unsubscribe": 1}
			),
			"Administrator's email must never be on the global Email Unsubscribe list",
		)

	def test_add_unsubscribe_still_unsubscribes_guest(self):
		"""Guest is not a real mailbox and should stay opted out of mail."""
		guest_email = frappe.db.get_value("User", "Guest", "email")
		frappe.db.delete("Email Unsubscribe", {"email": guest_email})

		add_unsubscribe()

		self.assertTrue(
			frappe.db.exists("Email Unsubscribe", {"email": guest_email, "global_unsubscribe": 1})
		)

	def test_get_site_default_email_domain_uses_site_not_example_com(self):
		from frappe.utils.install import get_site_default_email_domain

		self.assertEqual(get_site_default_email_domain(), frappe.local.site)
		self.assertNotEqual(get_site_default_email_domain(), "example.com")

	def test_patch_migrates_placeholder_admin_email_and_clears_unsubscribe(self):
		"""frappe.patches.v16_0.fix_admin_guest_placeholder_email must move a
		site still on the old admin@example.com placeholder to a deliverable,
		site-scoped address and remove any unsubscribe entry blocking it."""
		patch = importlib.import_module("frappe.patches.v16_0.fix_admin_guest_placeholder_email")

		frappe.db.set_value("User", "Administrator", "email", "admin@example.com", update_modified=False)
		if not frappe.db.exists("Email Unsubscribe", {"email": "admin@example.com"}):
			frappe.get_doc(
				{"doctype": "Email Unsubscribe", "email": "admin@example.com", "global_unsubscribe": 1}
			).insert(ignore_permissions=True)

		patch.execute()

		new_email = frappe.db.get_value("User", "Administrator", "email")
		self.assertEqual(new_email, f"admin@{frappe.local.site}")
		self.assertFalse(frappe.db.exists("Email Unsubscribe", {"email": "admin@example.com"}))
		self.assertFalse(
			frappe.db.exists("Email Unsubscribe", {"email": new_email, "global_unsubscribe": 1})
		)

	def test_patch_does_not_touch_already_customised_admin_email(self):
		"""A site that already set a real Administrator email must be left
		untouched by the migration -- it's not on the broken placeholder."""
		patch = importlib.import_module("frappe.patches.v16_0.fix_admin_guest_placeholder_email")

		frappe.db.set_value(
			"User", "Administrator", "email", "ops@my-real-domain.example", update_modified=False
		)

		patch.execute()

		self.assertEqual(
			frappe.db.get_value("User", "Administrator", "email"), "ops@my-real-domain.example"
		)

	def test_get_user_info_excludes_administrator_by_live_email(self):
		"""role.get_user_info must exclude Administrator/Guest by their
		*current* email, not a hardcoded admin@example.com/guest@example.com
		literal that a site may have already migrated away from."""
		from frappe.core.doctype.role.role import get_user_info

		frappe.db.set_value(
			"User", "Administrator", "email", "admin@custom-domain.example", update_modified=False
		)

		result = get_user_info([{"user_name": "Administrator"}], field="email")

		self.assertEqual(result, [])
