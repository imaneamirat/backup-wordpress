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
# Last modified: Oct 1, 2021
# Tested with : Python 3.8
# Script Revision: 0.1
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
from botocore.config import Config


# By Default, this script will read configuration from file /etc/backup-wp.conf
#
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
 

 
# create parser
parser = argparse.ArgumentParser()
 
# add arguments to the parser
parser.add_argument("--day",type=int,default=0)
parser.add_argument("--verbose",type=int,default=0)
 
# parse the arguments
args = parser.parse_args()

DAYTORESTORE=args.day
VERBOSE = args.verbose

CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')
BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')

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
else:
    print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
    exit(1)

# Getting current DateTime to create the separate backup folder like "20210921".

DATETIME = time.strftime('%Y%m%d')
TODAYRESTOREPATH = BACKUP_PATH + '/' + "RESTORE-" +DATETIME


# Checking if backup folder already exists or not. If not exists will create it.
try:
    os.stat(TODAYRESTOREPATH)
except:
    os.mkdir(TODAYRESTOREPATH)




# Part1 : Retrieve backup files

MysqlBackupFilename="wordpress.sql.gz"
WordPressBackupFilename="wordpress.site.tar.gz"

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
        S3_PATH = "DAYJ-" + DAYTORESTORE
    
    for filename in [MysqlBackupFilename,WordPressBackupFilename]:
        FileFullPath=pipes.quote(TODAYRESTOREPATH) + "/" + filename
        with open(FileFullPath, 'wb') as f:
            s3_client.download_file(S3_BUCKET,S3_PATH + "/" + filename,f)

    print ("")
    print ("Download from AWS S3 completed")   
    
else:
    print ("")
    print ("Starting Download from FTP Server")    
    
    ftpserver=tools.connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpserver.cwd(FTP_PATH)

    for file in [MysqlBackupFilename,WordPressBackupFilename]:
        print("Transfering" + file)
        result=tools.downloadftp(ftpserver,file,TODAYRESTOREPATH)

    tools.closeftp(ftpserver)

    print ("")
    print ("Copy to FTP Server completed")   

# Part2 : Database Restore.
print ("")
print ("Starting Import of MySQL Dump")

importcmd = "zcat " + pipes.quote(TODAYRESTOREPATH) + "/" + DB_NAME + ".sql.gz | mysql -h " + DB_HOST + DB_NAME

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
tar.extractall(WP_PATH)
tar.close()

print ("")
print ("Restore of  Wordpress Site folder completed")


print ("")
print ("Restore script completed")

