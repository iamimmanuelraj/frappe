import frappe


def execute():
	"""Move Administrator/Guest off the dead admin@example.com / guest@example.com
	placeholder addresses, and stop silently swallowing mail sent to Administrator.

	Context: every Frappe site has historically shipped with Administrator's
	email hardcoded to admin@example.com and Guest's to guest@example.com, and
	both addresses were unconditionally added to the Email Unsubscribe list on
	install. example.com never resolves, so mail to either address was always
	undeliverable; and even where it might have been deliverable (a site admin
	monitoring a real catch-all), the outright unsubscribe silently dropped
	Email Queue entries with no user-visible error.

	This was harmless while Administrator was hardcoded out of 2FA
	(frappe.twofactor.two_factor_is_enabled_for_), but once that exemption is
	removed, or SMTP/notification routing has any other reason to mail
	Administrator, a site with the unmodified default is unrecoverably locked
	out: the OTP email is queued, silently swallowed, and there is no console
	fallback if the operator only has web access.

	This patch is defensive/idempotent and safe to run on any site:
	  - Only touches Administrator/Guest if their email is still literally the
	    upstream placeholder; a site that already customised the address is
	    left untouched.
	  - Points the new address at the current site's own domain instead of a
	    domain the operator doesn't own, so at minimum the mail is
	    catch-all-able by whoever administers that domain.
	  - Removes any Email Unsubscribe row for Administrator's address so
	    outgoing mail to Administrator (2FA OTPs in particular) is no longer
	    silently dropped. Guest's unsubscribe entry is intentionally kept --
	    Guest is not a real mailbox and should stay opted out -- but is
	    re-pointed at the new address.
	"""
	site = getattr(frappe.local, "site", None)
	if not site:
		return

	_migrate_placeholder_user_email(
		user="Administrator",
		old_email="admin@example.com",
		new_email=f"admin@{site}",
		keep_unsubscribed=False,
	)
	_migrate_placeholder_user_email(
		user="Guest",
		old_email="guest@example.com",
		new_email=f"guest@{site}",
		keep_unsubscribed=True,
	)

	# Belt-and-braces: even if Administrator's email was already changed by
	# something else, it should never be on the unsubscribe list.
	current_admin_email = frappe.db.get_value("User", "Administrator", "email")
	if current_admin_email:
		frappe.db.delete(
			"Email Unsubscribe", {"email": current_admin_email, "global_unsubscribe": 1}
		)


def _migrate_placeholder_user_email(user, old_email, new_email, keep_unsubscribed):
	if not frappe.db.exists("User", user):
		return

	current_email = frappe.db.get_value("User", user, "email")
	if current_email != old_email:
		# Site already customised this address (or it's already been
		# migrated) -- leave it alone.
		return

	frappe.db.set_value("User", user, "email", new_email, update_modified=False)

	# Move the corresponding Email Unsubscribe row, if any, to the new address
	# instead of leaving a stale entry for an address nobody uses anymore.
	if frappe.db.exists("Email Unsubscribe", {"email": old_email}):
		if keep_unsubscribed:
			frappe.db.set_value(
				"Email Unsubscribe", {"email": old_email}, "email", new_email, update_modified=False
			)
		else:
			frappe.db.delete("Email Unsubscribe", {"email": old_email})
