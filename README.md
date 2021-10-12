This script backups WordPress data to either FTP server or AWS S3 depending on the configuration parameters
It will make backup of wordpress MySQL database and wordpress Apache folder  
Backup process follow a Backup Folder Rotation Strategy using RETENTION parameter
By Default, this script will read configuration from file /etc/backup-wp.conf
Todo : Add the option -f to read parameters from a specified filename in the command line parameter

Verbose mode :
Set VERBOSE=0 to disable logs display
Set VERBOSE=1 to have minimal logs display
Set VERBOSE=2 to have full logs display

Example for RETENTION = 7

Init :
Create the following folders :

/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6

Before each new daily backup  :

1) Rotation :

rmdir /data/backup/day-J-6 
mv /data/backup/day-J-5 to /data/backup/dayJ-6
mv /data/backup/day-J-4 to /data/backup/dayJ-5
mv /data/backup/day-J-3 to /data/backup/dayJ-4
mv /data/backup/day-J-2 to /data/backup/dayJ-3
mv /data/backup/day-J-1 to /data/backup/dayJ-2
mv /data/backup/day-J to /data/backup/dayJ-1
mkdir /data/backup/dayJ

2) copy new backup files in /data/backup/dayJ


Example of config file content : /etc/backup-wp.conf

[WP]
WP_PATH=/var/www/html
[DB]
DB_HOST=localhost
DB_NAME=wordpress

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
BACKUP_RETENTION=7
BACKUP_DEST=FTP
FTP_SERVER=ftp.imaneaic.com
FTP_USER=backupwp
FTP_PASSWD=1edd!ai3$
FTP_PATH=backup-wp


Create the file .my.cnf in your HOME directory :
Content of .my.cnf :

[client]
host=localhost
user=wpu
password=Imane$2021!
[mysqldump]
host=localhost
user=wpu
password=Imane$2021!






