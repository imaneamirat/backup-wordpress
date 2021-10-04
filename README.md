By Default, this script will read configuration from file /etc/backup-wp.conf
Todo : Add the option -f to read parameters from a specified filename in the command line parameter
Todo : Backup Folder Rotation Strategy

Backup folders :

Create the following folders :

/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6
/data/backup/dayJ-7

Before each new daily backup  :

1) Rotation :

/data/backup/day-J-7 rm files
/data/backup/day-J-6 mv to /data/backup/dayJ-7
/data/backup/day-J-5 mv to /data/backup/dayJ-6
/data/backup/day-J-4 mv to /data/backup/dayJ-5
/data/backup/day-J-3 mv to /data/backup/dayJ-4
/data/backup/day-J-2 mv to /data/backup/dayJ-3
/data/backup/day-J-1 mv to /data/backup/dayJ-2
/data/backup/day-J mv to /data/backup/dayJ-1

2) copy new backup files in /data/backup/dayJ


Example of config file content :

[WP]
WP_PATH=/var/www/html
[DB]
DB_HOST=localhost
DB_NAME=wordpress
DB_USERNAME=wpu
DB_PASSWORD=Imane$2021!
[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_DEST=S3
S3_BUCKET=ImaneAIC-WP
S3_ACCESS_KEY=XXXXXXXXXXX
S3_SECRET_ACCESS_KEY=YYYYYYYY
S3_DEFAULT_REGION=eu-west-3

Or
[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_DEST=FTP
FTP_SERVER=ftp.imaneaic.com
FTP_USER=backupwp
FTP_PASSWD=1edd!ai3$
FTP_PATH=backup-wp
'''




