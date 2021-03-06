#!/usr/bin/python3

###########################################################
#
# This python script is used to restore Wordpress website and associated mysql database
# using mysql and tar utility.
# Backups are downloaded from either :
# - AWS S3 and encrypted using a private AES-256 key
# or
# - FTP server
#
# This scripts needs root privileges
#
# Written by : Imane AMIRAT
# Created date: Sept 30, 2021
# Last modified: Oct 22, 2021
# Tested with : Python 3.8
# Script Revision: 0.9
#
##########################################################

# Import required python libraries

import os
import shutil
import errno
import time
import datetime
import pipes
import sys
import configparser
import tarfile
import boto3
import ftplib
import tools
import random
import argparse
import encrypt
from botocore.config import Config


# By Default, this script will read configuration from file /etc/backup-wp.conf
#
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
'''
1) Copy files from remote location ie FTP or S3 to /data/backup/RESTORE-DATE
2) Decrypt files
3) Import SQL backup in MySQL
4) Untar Site backup
'''
CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

SMTP_HOST = config.get('SMTP','SMTP_HOST')
SMTP_FROM = config.get('SMTP','SMTP_FROM')
SMTP_TO = config.get('SMTP','SMTP_TO')

BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')
BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')

ENCRYPTION_KEYPATH = config.get('ENCRYPT','KEYPATH')

# create parser
parser = argparse.ArgumentParser()

# add arguments to the parser
parser.add_argument("-d","--day",type=int,default=0,help="index of day in the past to be restored. Possible value from 0 to BACKUP_RETENTION - 1")
parser.add_argument("-l","--local",action='store_true', help="Restore from local backup folders only")
parser.add_argument("-v","--verbose",type=int,default=0,choices=[0,1,2],help="0 disable verbose, 1 minimal verbose, 2 debug mode")

# parse the arguments
args = parser.parse_args()

DAYTORESTORE=args.day
VERBOSE = args.verbose
LOCALRESTORE = args.local

if LOCALRESTORE:
    BACKUP_DEST = 'LOCAL'

if BACKUP_DEST == 'S3':
    S3_BUCKET = config.get('BACKUP','S3_BUCKET')
    S3_ACCESS_KEY = config.get('BACKUP','S3_ACCESS_KEY')
    S3_SECRET_ACCESS_KEY = config.get('BACKUP','S3_SECRET_ACCESS_KEY')
    S3_DEFAULT_REGION = config.get('BACKUP','S3_DEFAULT_REGION')
elif BACKUP_DEST == 'FTP':
    FTP_SERVER = config.get('BACKUP','FTP_SERVER')
    FTP_USER = config.get('BACKUP','FTP_USER')
    FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
    FTP_PATH = config.get('BACKUP','FTP_PATH')
elif BACKUP_DEST == 'LOCAL':
    pass
else:
    print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
    exit(1)

if BACKUP_DEST == 'LOCAL':
    if DAYTORESTORE:
        TODAYRESTOREPATH = BACKUP_PATH + '/' + "DAYJ-" + str(DAYTORESTORE)
    else:
        TODAYRESTOREPATH = BACKUP_PATH + '/' + "DAYJ"

else:
    # Getting current DateTime to create the separate backup folder like "20210921".

    DATETIME = time.strftime('%Y%m%d')
    TODAYRESTOREPATH = BACKUP_PATH + '/' + "RESTORE-" +DATETIME


    # Checking if backup folder already exists or not. If not exists will create it.
    try:
        os.stat(TODAYRESTOREPATH)
    except:
        os.mkdir(TODAYRESTOREPATH)




# Part1 : Retrieve backup files

MysqlBackupFilename="wordpress.sql.gz.bin"
WordPressBackupFilename="wordpress.site.tar.gz.bin"

if BACKUP_DEST == 'S3':
    print ("")
    print ("Starting Download from AWS S3")

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

    if DAYTORESTORE == 0:
        S3_PATH = "DAYJ"
    else:
        S3_PATH = "DAYJ-" + str(DAYTORESTORE)

    for filename in [MysqlBackupFilename,WordPressBackupFilename]:
        FileFullPath=pipes.quote(TODAYRESTOREPATH) + "/" + filename
        KEY=S3_PATH + "/" + filename
        with open(FileFullPath, 'wb') as f:
            try:
                s3_client.download_file(Bucket=S3_BUCKET,Key=KEY,Filename=FileFullPath)
            except:
                if VERBOSE == 2:
                    print("Error during download of " + KEY)
                exit(1)


    print ("")
    print ("Download from AWS S3 completed")

elif BACKUP_DEST == 'FTP':
    print ("")
    print ("Starting Download from FTP Server")

    if DAYTORESTORE == 0:
        RESTORE_FOLDER = "DAYJ"
    else:
        RESTORE_FOLDER = "DAYJ-" + str(DAYTORESTORE)
    ftpserver=tools.connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpserver.cwd(FTP_PATH + "/" + RESTORE_FOLDER)

    for file in [MysqlBackupFilename,WordPressBackupFilename]:
        print("Transfering" + file)
        result=tools.downloadftp(ftpserver,file,TODAYRESTOREPATH)

    tools.closeftp(ftpserver)

    print ("")
    print ("Copy to FTP Server completed")


# Part 2 : Decrypt files
fdKey = open(ENCRYPTION_KEYPATH,'rb')
ENCRYPTION_KEY = fdKey.read()

for file in [MysqlBackupFilename,WordPressBackupFilename]:
    print("Decrypting " + file)
    result=encrypt.decrypt_file(TODAYRESTOREPATH + "/" + file,ENCRYPTION_KEY)

# Part3 : Database Restore.
print ("")
print ("Starting Import of MySQL Dump")

importcmd = "zcat " + pipes.quote(TODAYRESTOREPATH) + "/" + DB_NAME + ".sql.gz | mysql -h " + DB_HOST + " " + DB_NAME

os.system(importcmd)


print ("")
print ("Dump of MySQL imported")

# Part3 : WP Site Restore.

print ("")
print ("Starting Restore of Wordpress Site folder")
#declare filename
wp_archive= TODAYRESTOREPATH + "/" + "wordpress.site.tar.gz"

#open file in read mode
tar = tarfile.open(wp_archive,"r:gz")
tar.extractall("/")
tar.close()

print ("")
print ("Restore of  Wordpress Site folder completed")


print ("")
print ("Restore script completed")

