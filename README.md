# Description of the project
Set of scripts to make backup and restore of a complete WordPress server

## Composition

- backup-wp.py :

Scripts to backup WordPress data to either FTP server or AWS S3 depending on the configuration parameters.

It will make backup of wordPress MySQL database and WordPress Apache folder

Backup process follows a Backup Folder Rotation Strategy using RETENTION parameter

By Default, this script will read configuration from file /etc/backup-wp.conf

Todo :

Add the option -f to read parameters from a specified filename in the command line parameter

Needs Python 3

Tested on Python 3.9
```
usage: backup-wp.py [-h] [-v {0,1,2}]

optional arguments:
  -h, --help            show this help message and exit
  -v {0,1,2}, --verbose {0,1,2}
                        0 disable verbose, 1 minimal verbose, 2 debug mode

```
- restore-wp.py :

Scripts to restore WordPress data to either FTP server or AWS S3 depending on the configuration parameters

It will first copy MySQL database backups and WordPress site archive from either FTP server or AWS S3 depending on the configuration parameters to a local restore repository then import the SQL backup and untar the site archive to the WordPress website location

By Default, this script will read configuration from file /etc/backup-wp.conf

Todo : Add the option -f to read parameters from a specified filename in the command line parameter

Needs Python 3

Tested on Python 3.9
```
usage: restore-wp.py [-h] [-d DAY] [-v {0,1,2}]

optional arguments:
  -h, --help            show this help message and exit
  -l, --local           Use local backup folders only
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

- wp_make_clean_install_and_restore_from_backup.yml

Ansible playbook to install a complete WordPress server on a fresh new Debian 11 server

ie install Apache2 + PHP7 + MySQL-server 5.7  then restore WordPress Site and Database dump from backup

```
Usage :
Define wordpress host in the ansible inventory

Needs the files backup-wp.conf and AES.key to be present in the same directory.

These files have to be the same as the ones on the original WordPress server

ansible-playbook wp_make_clean_install_and_restore_from_backup.yml
```


- wp_copy_backup_scripts.yml

Ansible playbook to install backup and restore scripts with all the required dependencies

```
Usage :
Define wordpress host in the ansible inventory

Needs the files backup-wp.conf and AES.key to be present in the same directory.

If AES.key is not already created you can create a new AES.key file by using the python file create_key.py
```

## Verbose mode :

Set VERBOSE=0 to disable logs display

Set VERBOSE=1 to have minimal logs display

Set VERBOSE=2 to have full logs display

Example for RETENTION = 7

# Explanation of the "Backup" backup-wp.py process :

## Init : First time execution of the backup process

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
## Before each new daily backup: Rotation :
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
## Backup process itself :
1. Make new backup files in /data/backup/dayJ

2. Encrypt using AES 256

3. Copy on the remote location using the same Rotation Strategy

# Explanation of the "Restore" restore-wp.py process :
1. Retrieve backup files from remote location
By default the script will retrieve files from  remote folder dayJ

This value can be changed with the parameter "-d Number" to retrieve from remote folder "dayJ-Number"

The backup files are copied locally in the folder /data/backup/RESTORE-DATE

2. Decrypt using AES 256

3. Import SQL backup  in MySQL and untar Site backup in WordPress Apache folder

# Configuration files :
## Example of config file content : /etc/backup-wp.conf
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
BACKUP_RETENTION=7
BACKUP_DEST=FTP
FTP_SERVER=ftp.imaneaic.com
FTP_USER=backupwp
FTP_PASSWD=1edd!ai3$
FTP_PATH=backup-wp
```

## Example of content for the file .my.cnf that needs to be present in your Wordpress user's HOME directory :

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