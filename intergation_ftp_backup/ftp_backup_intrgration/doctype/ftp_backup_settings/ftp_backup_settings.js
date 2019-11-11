// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('FTP Backup Settings', {
	refresh: function(frm) {
		frm.clear_custom_buttons();
		frm.events.take_backup(frm);
	},

	take_backup: function(frm) {
		if (frm.doc.enabled && (frm.doc.ftp_authentication=='Anonymous' || (frm.doc.ftp_username && frm.doc.ftp_password))) {
			frm.add_custom_button(__("Take Backup Now"), function(frm){
				frappe.call({
					method: "intergation_ftp_backup.ftp_backup_intrgration.doctype.ftp_backup_settings.ftp_backup_settings.take_backup",
					freeze: true
				})
			}).addClass("btn-primary")
		}
	}
});

