## FTP Backup Intrgration

Very early production stage. Use at your own risk.

- Add FTP backup functionality
- Tested lightly  on v11 only (Python 3.6.3).


## Hack

- Currently reports file upload as 'uploaded_to_dropbox' which is registered in [HERE](https://github.com/frappe/frappe/blob/61f98c6ce9ed187570a7ae16a694e06acf7e8c43/frappe/core/doctype/file/file.json#L27-L28) and [HERE](https://github.com/frappe/frappe/blob/61f98c6ce9ed187570a7ae16a694e06acf7e8c43/frappe/core/doctype/file/file.json#L158-L171)

#### License

MIT

## Frappe Install
```bash
bench get-app intergation_ftp_backup https://github.com/aleksas/frappe_ftp_backup_integration.git
bench --site site1.local install-app intergation_ftp_backup
```

## Bench execute

```bash
bench execute intergation_ftp_backup.ftp_backup_intrgration.doctype.ftp_backup_settings.ftp_backup_settings.take_backup_to_ftp
```

## Settings 

![image](https://user-images.githubusercontent.com/594470/68489590-161f2300-0250-11ea-9376-09100aac07e1.png)
