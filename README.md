Set of scripts to make backup and restore of a complete Wordpress server

Composed of

- backup-wp.py :

Scripts to backup WordPress data to either FTP server or AWS S3 depending on the configuration parameters.

It will make backup of wordpress MySQL database and wordpress Apache folder

Backup process follow a Backup Folder Rotation Strategy using RETENTION parameter

By Default, this script will read configuration from file /etc/backup-wp.conf

Todo : Add the option -f to read parameters from a specified filename in the command line parameter

Needs Python 3

Tested on Python 3.10
```
usage: backup-wp.py [-h] [-v {0,1,2}]

optional arguments:
  -h, --help            show this help message and exit
  -v {0,1,2}, --verbose {0,1,2}
                        0 disable verbose, 1 minimal verbose, 2 debug mode

```
- restore-wp.py :
Scripts to restore WordPress data to either FTP server or AWS S3 depending on the configuration parameters

It will first copy MySQL database backups and Wordpress site archive from either FTP server or AWS S3 depending on the configuration parameters to a local restore repository then import the SQL backup and untar the site archive to the wordpress website location

By Default, this script will read configuration from file /etc/backup-wp.conf

Todo : Add the option -f to read parameters from a specified filename in the command line parameter

Needs Python 3

Tested on Python 3.10
```
usage: restore-wp.py [-h] [-d DAY] [-v {0,1,2}]

optional arguments:
  -h, --help            show this help message and exit
  -d DAY, --day DAY     index of day in the past to be restored. Possible value from 0 to BACKUP_RETENTION - 1
  -v {0,1,2}, --verbose {0,1,2}
                        0 disable verbose, 1 minimal verbose, 2 debug mode
```
- tools.py
Set of functions used by both backup and restore scripts

- create-key.py
Script to create a 256 bits key used for encryption
```
usage: create-key.py [-h] [--path PATH]

optional arguments:
  -h, --help   show this help message and exit
  --path PATH
```
- encrypt.py
Set of functions used for encrypt en decrypt using AES-256

- wp_make_clean_install.yml
Ansible playbook to install a complete WordPress server on a fresh new Debian 11 server
ie install Apache2 + PHP7 + MySQL-server 5.7 + WordPress

```
Usage :
Define wordpress host in the ansible inventory

ansible-playbook wp_make_clean_install.yml
```

- wp_restore_after_clean_install.yml
Ansible playbook to restore a WordPress backup on a clean WordPress install

```
Usage :
Define wordpress host in the ansible inventory
Needs the files backup-wp.conf and AES.key to be present in the same location
These files has to be the same as the ones on the original WordPress server

ansible-playbook wp_restore_after_clean_install.yml
```

Verbose mode :

Set VERBOSE=0 to disable logs display

Set VERBOSE=1 to have minimal logs display

Set VERBOSE=2 to have full logs display

Example for RETENTION = 7

Init :

Create the following folders :
```
/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6
```
Before each new daily backup  :

1) Rotation :
```
rmdir /data/backup/day-J-6
mv /data/backup/day-J-5 to /data/backup/dayJ-6
mv /data/backup/day-J-4 to /data/backup/dayJ-5
mv /data/backup/day-J-3 to /data/backup/dayJ-4
mv /data/backup/day-J-2 to /data/backup/dayJ-3
mv /data/backup/day-J-1 to /data/backup/dayJ-2
mv /data/backup/day-J to /data/backup/dayJ-1
mkdir /data/backup/dayJ
```
2) copy new backup files in /data/backup/dayJ


Example of config file content : /etc/backup-wp.conf
```
[WP]
WP_PATH=/var/www/html
[DB]
DB_HOST=localhost
DB_NAME=wordpress
[SMTP]
SMTP_HOST=localhost
SMTP_FROM=address@example.com
SMTP_TO=address@recipient.com

[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_DEST=S3
S3_BUCKET=ImaneAIC-WP
S3_ACCESS_KEY=XXXXXXXXXXX
S3_SECRET_ACCESS_KEY=YYYYYYYY
S3_DEFAULT_REGION=eu-west-3
```
Or
```
[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_RETENTION=7
BACKUP_DEST=FTP
FTP_SERVER=ftp.imaneaic.com
FTP_USER=backupwp
FTP_PASSWD=1edd!ai3$
FTP_PATH=backup-wp
```

Create the file .my.cnf in your HOME directory :

Content of .my.cnf :
```
[client]
host=localhost
user=wpu
password=Imane$2021!
[mysqldump]
host=localhost
user=wpu
password=Imane$2021!
```