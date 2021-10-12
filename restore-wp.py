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
import time
import datetime
import pipes
import sys
import configparser
import tarfile
import boto3
import ftplib
from botocore.config import Config


# By Default, this script will read configuration from file /etc/backup-wp.conf
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
# Todo : Backup Folder Rotation Strategy
'''
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
'''


def connectftp(ftpserver = "172.16.30.32" , username = 'anonymous', password = 'anonymous@', passive = False):
    """connect to ftp server and open a session
       - ftpserver: IP address of the ftp server
       - username: login of the ftp user ('anonymous' by défaut)
       - password: password of the ftp user ('anonymous@' by défaut)
       - passive: activate or disable ftp passive mode (False par défaut)
       return the object 'ftplib.FTP' after connection and opening of a session
    """
    ftp = ftplib.FTP()
    ftp.connect(ftpserver)
    ftp.login(username, password)
    ftp.set_pasv(passive)
    return ftp

def downloadftp(ftp, ficftp, repdsk='.', ficdsk=None):
    """Download the file ficftp from ftpserver and put it in the local folder repdsk
       - ftp: object 'ftplib.FTP' from an open session
       - ficftp: name of the file to download
       - repdsk: local folder where you want to store the file
       - ficdsk: optional, if you want to rename the file locally 
    """
    if ficdsk==None:
        ficdsk=ficftp
    with open(os.path.join(repdsk, ficdsk), 'wb') as f:
        ftp.retrbinary('RETR ' + ficftp, f.write)

def uploadftp(ftp, ficdsk,ftpPath):
    '''
    Upload the file ficdsk from local folder to the current ftp folder
        - ftp: object 'ftplib.FTP' on an open session
        - ficdsk: local name of the file to upload
        - ficPath: FTP path where to store the file
    '''
    repdsk, ficdsk2 = os.path.split(ficdsk)
    ficftp = ftpPath + "/" + ficdsk2
    with open(ficdsk, "rb") as f:
        ftp.storbinary("STOR " + ficftp, f)

def closeftp(ftp):
    """Close FTP connection
       - ftp: variable 'ftplib.FTP' on open connection
    """
    try:
        ftp.quit()
    except:
        ftp.close() 

CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')


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
TODAYRESTOREPATH = BACKUP_PATH + '/' + DATETIME

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

    for filename in [MysqlBackupFilename,WordPressBackupFilename]:
        FileFullPath=pipes.quote(TODAYRESTOREPATH) + "/" + filename
        with open(FileFullPath, 'wb') as f:
            s3_client.download_file(S3_BUCKET,filename,f)

    print ("")
    print ("Download from AWS S3 completed")   
    
else:
    print ("")
    print ("Starting Download from FTP Server")    
    
    ftpaws=connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpaws.cwd(FTP_PATH)

    for file in [MysqlBackupFilename,WordPressBackupFilename]:
        print("Transfering" + file)
        result=downloadftp(ftpaws,file,TODAYRESTOREPATH)

    closeftp(ftpaws)

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

