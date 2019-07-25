from ftplib import FTP, error_perm

ftp = FTP('f', 'alex', 'Aoiujkl')

def ftp_mkdirs(path):  

    def mkdirs_(currentDir):
        if currentDir != "":
            try:
                ftp.cwd(currentDir)
            except error_perm:
                mkdirs_('/'.join(currentDir.split('/')[:-1]))
                ftp.mkd(currentDir)
                ftp.cwd(currentDir)

    pwd = ftp.pwd()
    path = '/'.join([pwd.rstrip('/'), path.lstrip('/')])

    mkdirs_(path)

ftp_mkdirs("user-backups/alex/backups/as/as")
ftp_mkdirs("user-backups/alex/backups/as/asd")