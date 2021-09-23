#!/usr/bin/python3

###########################################################
#
# This python script is used to backup Wordpress website and associated mysql database
# using mysqldump and tar utility.
# Backups are copied to AWS S3 and encrypted using a private AES-256 key
# This scripts needs root privileges
#
# Written by : Imane AMIRAT
# Created date: Sept 21, 2021
# Last modified: Aug 21, 2021
# Tested with : Python 3.8
# Script Revision: 0.3
#
##########################################################

# Import required python libraries

import os
import time
import datetime
import pipes
import sys
import configparser
import tarfile
import boto3
from botocore.config import Config

# By Default, this script will read configuration from file /etc/backup-wp.conf
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter

CONFIG_FILE = '/etc/backup-wp.conf'

'''
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
S3_BUCKET=ImaneAIC-WP
S3_ACCESS_KEY=XXXXXXXXXXX
S3_SECRET_ACCESS_KEY=YYYYYYYY
S3_DEFAULT_REGION=eu-west-3
'''

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')
DB_USERNAME = config.get('DB','DB_USERNAME')
DB_PASSWORD = config.get('DB','DB_PASSWORD')
BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')

S3_BUCKET = config.get('BACKUP','S3_BUCKET')
S3_ACCESS_KEY = config.get('BACKUP','S3_ACCESS_KEY')
S3_SECRET_ACCESS_KEY = config.get('BACKUP','S3_SECRET_ACCESS_KEY')
S3_DEFAULT_REGION = config.get('BACKUP','S3_DEFAULT_REGION')

# Getting current DateTime to create the separate backup folder like "20210921".
DATETIME = time.strftime('%Y%m%d')
TODAYBACKUPPATH = BACKUP_PATH + '/' + DATETIME

# Checking if backup folder already exists or not. If not exists will create it.
try:
    os.stat(TODAYBACKUPPATH)
except:
    os.mkdir(TODAYBACKUPPATH)

# Part1 : Database backup.
print ("")
print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " -u " + DB_USERNAME + " -p\'" + DB_PASSWORD + "\' " + DB_NAME + " > " + pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql"

os.system(dumpcmd)
gzipcmd = "gzip " + pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql"
os.system(gzipcmd)
localMysqlBackup=pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql.gz"

print ("")
print ("Backup of MySQL completed")

# Part2 : WP Site backup.

print ("")
print ("Starting backup of Wordpress Site folder")
#declare filename
wp_archive= TODAYBACKUPPATH + "/" + "wordpress.site.tar.gz"

#open file in write mode
tar = tarfile.open(wp_archive,"w:gz")
tar.add(WP_PATH)
tar.close()

print ("")
print ("Backup of  Wordpress Site folder completed")


# Part 3 : Copy to S3

print ("")
print ("Starting Copy to AWS S3")

bucket_name = S3_BUCKET # name of the bucket

my_config = Config(
    region_name = S3_DEFAULT_REGION,
    retries = {
        'max_attempts': 10,
        'mode': 'standard'
    }
)


s3_client = boto3.client(
    's3',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY, 
    config=my_config
)

for file_name in [localMysqlBackup,wp_archive]:
    finaldest=DATETIME + "/" + os.path.basename(file_name)
    s3_client.upload_file(file_name, S3_BUCKET, finaldest)

print ("")
print ("Backup script completed")
print ("Your backups have been created in '" + TODAYBACKUPPATH + "' directory")
