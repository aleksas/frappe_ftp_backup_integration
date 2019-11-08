# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
import json
from frappe import _
from frappe.model.document import Document
from ftplib import FTP, FTP_TLS, error_perm
from frappe.utils.backups import new_backup
from frappe.utils.background_jobs import enqueue
from six.moves.urllib.parse import urlparse, parse_qs
from frappe.integrations.utils import make_post_request
from rq.timeouts import JobTimeoutException
from frappe.utils import (cint, split_emails,
	get_files_path, get_backups_path, get_url, encode)
from six import text_type
from ftplib import FTP, FTP_TLS
from dateutil import parser

ignore_list = [".DS_Store"]

class FTPBackupSettings(Document):
	def validate(self):
		if self.enabled and self.limit_no_of_backups and self.no_of_backups < 1:
			frappe.throw(_('Number of DB backups cannot be less than 1'))

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to ftp"""
	enqueue("intergation_ftp_backup.ftp_backup_intrgration.doctype.ftp_backup_settings.ftp_backup_settings.take_backup_to_ftp", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))

def take_backups_daily():
	take_backups_if("Daily")

def take_backups_weekly():
	take_backups_if("Weekly")

def take_backups_if(freq):
	if frappe.db.get_value("FTP Backup Settings", None, "backup_frequency") == freq:
		take_backup_to_ftp()

def take_backup_to_ftp(retry_count=0, upload_db_backup=True):
	did_not_upload, error_log = [], []
	try:
		if cint(frappe.db.get_value("FTP Backup Settings", None, "enabled")):
			did_not_upload, error_log = backup_to_ftp(upload_db_backup)
			if did_not_upload: raise Exception

			send_email(True, "FTP")
	except JobTimeoutException:
		if retry_count < 2:
			args = {
				"retry_count": retry_count + 1,
				"upload_db_backup": False #considering till worker timeout db backup is uploaded
			}
			enqueue("intergation_ftp_backup.ftp_backup_intrgration.doctype.ftp_backup_settings.ftp_backup_settings.take_backup_to_ftp",
				queue='long', timeout=1500, **args)
	except Exception:
		if isinstance(error_log, str):
			error_message = error_log + "\n" + frappe.get_traceback()
		else:
			file_and_error = [" - ".join(f) for f in zip(did_not_upload, error_log)]
			error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
		frappe.errprint(error_message)
		send_email(False, "FTP", error_message)

def send_email(success, service_name, error_status=None):
	if success:
		if frappe.db.get_value("FTP Backup Settings", None, "send_email_for_successful_backup") == '0':
			return

		subject = "Backup Upload Successful"
		message ="""<h3>Backup Uploaded Successfully</h3><p>Hi there, this is just to inform you
		that your backup was successfully uploaded to your %s account. So relax!</p>
		""" % service_name

	else:
		subject = "[Warning] Backup Upload Failed"
		message ="""<h3>Backup Upload Failed</h3><p>Oops, your automated backup to %s
		failed.</p>
		<p>Error message: <br>
		<pre><code>%s</code></pre>
		</p>
		<p>Please contact your system manager for more information.</p>
		""" % (service_name, error_status)

	if not frappe.db:
		frappe.connect()

	recipients = split_emails(frappe.db.get_value("FTP Backup Settings", None, "send_notifications_to"))
	frappe.sendmail(recipients=recipients, subject=subject, message=message)

def combine_path(root_dir, dst_dir):
	return '/'.join([] + root_dir.rstrip('/').split('/') + dst_dir.strip('/').split('/'))

def backup_to_ftp(upload_db_backup=True):
	if not frappe.db:
		frappe.connect()

	# upload database
	ftp_settings, use_tls, root_directory, file_backup, limit_no_of_backups, no_of_backups  = get_ftp_settings()

	if not ftp_settings['host']:
		return 'Failed backup upload', 'No FTP host! Please enter valid host for FTP.'

	if not ftp_settings['user']:
		return 'Failed backup upload', 'No FTP username! Please enter valid username for FTP.'

	if not root_directory:
		return 'Failed backup upload', 'No FTP username! Please enter valid username for FTP.'

	ftp_client = FTP_TLS(**ftp_settings) if use_tls else FTP(**ftp_settings)

	try:
		if upload_db_backup:
			backup = new_backup(ignore_files=True)
			filename = os.path.join(get_backups_path(), os.path.basename(backup.backup_path_db))
			upload_file_to_ftp(filename, combine_path(root_directory, "/database"), ftp_client)

			# delete older databases
			if limit_no_of_backups:
				delete_older_backups(ftp_client, combine_path(root_directory, "/database"), no_of_backups)

		# upload files to files folder
		did_not_upload = []
		error_log = []

		if file_backup:
			upload_from_folder(get_files_path(), 0, combine_path(root_directory, "/files"), ftp_client, did_not_upload, error_log)
			upload_from_folder(get_files_path(is_private=1), 1, combine_path(root_directory, "/private/files"), ftp_client, did_not_upload, error_log)

		return did_not_upload, list(set(error_log))

	finally:
		ftp_client.quit()

def upload_from_folder(path, is_private, ftp_folder, ftp_client, did_not_upload, error_log):
	if not os.path.exists(path):
		return

	if is_fresh_upload():
		response = get_uploaded_files_meta(ftp_folder, ftp_client)
	else:
		response = frappe._dict({"entries": []})

	path = text_type(path)

	for f in frappe.get_all("File", filters={"is_folder": 0, "is_private": is_private,
		"uploaded_to_dropbox": 0}, fields=['file_url', 'name', 'file_name']):
		if is_private:
			filename = f.file_url.replace('/private/files/', '')
		else:
			if not f.file_url:
				f.file_url = '/files/' + f.file_name
			filename = f.file_url.replace('/files/', '')
		filepath = os.path.join(path, filename)

		if filename in ignore_list:
			continue

		found = False
		for file_metadata in response.entries:
			try:
				if (os.path.basename(filepath) == file_metadata.name
					and os.stat(encode(filepath)).st_size == int(file_metadata.size)):
					found = True
					update_file_ftp_status(f.name)
					break
			except Exception:
				error_log.append(frappe.get_traceback())

		if not found:
			try:
				upload_file_to_ftp(filepath, ftp_folder, ftp_client)
				update_file_ftp_status(f.name)
			except Exception:
				did_not_upload.append(filepath)
				error_log.append(frappe.get_traceback())

def upload_file_to_ftp(filename, folder, ftp_client):
	"""upload files with chunk of 15 mb to reduce session append calls"""
	if not os.path.exists(filename):
		return

	with open(encode(filename), 'rb') as f:
		path = "{0}/{1}".format(folder, os.path.basename(filename))

		try:
			create_folder_if_not_exists(ftp_client, folder)
			pwd = ftp_client.pwd()
			ftp_client.cwd(folder)

			ftp_client.storbinary('STOR %s' % os.path.basename(filename), f)
			
			ftp_client.cwd(pwd)
		except Exception:
			error = "File Path: {path}\n".format(path=path)
			error += frappe.get_traceback()
			frappe.log_error(error)
			print (error)
		
def create_folder_if_not_exists(ftp_client, path):
	def _mkdirs_(currentDir):
		if currentDir != "":
			try:
				ftp_client.cwd(currentDir)
			except error_perm:
				_mkdirs_('/'.join(currentDir.split('/')[:-1]))
				ftp_client.mkd(currentDir)
				ftp_client.cwd(currentDir)

	pwd = ftp_client.pwd()
	path = '/'.join([pwd.rstrip('/'), path.lstrip('/')])
	_mkdirs_(path)
	ftp_client.cwd(pwd)

def update_file_ftp_status(file_name):
	frappe.db.set_value("File", file_name, 'uploaded_to_dropbox', 1, update_modified=False)

def is_fresh_upload():
	file_name = frappe.db.get_value("File", {'uploaded_to_dropbox': 1}, 'name')
	return not file_name

def get_uploaded_files_meta(ftp_folder, ftp_client):
	try:
		return {'entries': ftp_client.nlst(ftp_folder) }
	except error_perm as e:
		if str(e) == "550 No files found":
			return {'entries': [] }
		else:
			raise

def decorate_files(ftp_client, filenames):
    latest_time = None

    for name in filenames:
        time = ftp_client.voidcmd("MDTM " + name)
        if (latest_time is None) or (time > latest_time):
            latest_time = time
        
        yield name, latest_time

def get_ftp_settings():
	print ('get_ftp_settings')
	settings = frappe.get_doc("FTP Backup Settings")

	app_details = {
		"host": settings.ftp_host,
		"user": 'anonymous' if settings.ftp_authentication == 'Anonymous' else settings.ftp_username,
		"passwd": '' if settings.ftp_authentication == 'Anonymous' else settings.get_password(fieldname="ftp_password", raise_exception=False)
	}

	return app_details, settings.ftp_tls, settings.ftp_root_directory, settings.file_backup, settings.limit_no_of_backups, settings.no_of_backups 

def delete_older_backups(ftp_client, folder_path, to_keep):
	print ('delete_older_backups')
	res = get_uploaded_files_meta(folder_path, ftp_client, )
	files = []
	for ft in decorate_files(ftp_client, res['entries']):
		files.append(ft)

	if len(files) <= to_keep:
		return

	files.sort(key=lambda item:item[1], reverse=True)
	for f, _ in files[to_keep:]:
		print ('delete', f)
		ftp_client.delete(f)

