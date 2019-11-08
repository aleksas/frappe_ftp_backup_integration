## FTP Backup Intrgration

Very early production stage. Use at your own risk.

- Add FTP backup functionality
- Tested lightly  on v11 only.


## Hack

- Currently reports file upload as 'uploaded_to_dropbox' which is registered in [HERE](https://github.com/frappe/frappe/blob/version-11/frappe/core/doctype/file/file.json#L701)

#### License

MIT

## Frappe Install
`bench get-app intergation_ftp_backup https://github.com/aleksas/frappe_ftp_backup_integration.git`
`bench --site site1.local install-app intergation_ftp_backup`

## Settings 

![image](https://user-images.githubusercontent.com/594470/68489590-161f2300-0250-11ea-9376-09100aac07e1.png)
