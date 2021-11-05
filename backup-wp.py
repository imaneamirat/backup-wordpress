#!/usr/bin/python3

###########################################################
#
# This python script is used to backup Wordpress website and associated mysql database
# using mysqldump and tar utility.
# Backups are copied to either :
# - AWS S3
# or
# - FTP server
# and encrypted using a private AES-256 key
# Needs privileges to access Wordpress site files and Wordpress database
# and write access to backup local folders
#
# Written by : Imane AMIRAT
# Created date: Jul 24, 2021
# Last modified: Nov 05, 2021
# Tested with : Python 3.9
# Script Revision: 1.1
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
import argparse
import Crypto
import encrypt
from botocore.config import Config




# By Default, this script will read configuration from file /etc/backup-wp.conf
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
# Todo : File integrity check
'''
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
'''
# create parser
parser = argparse.ArgumentParser()

# add arguments to the parser
parser.add_argument("-v","--verbose",type=int,default=0,choices=[0,1,2],help="0 disable verbose, 1 minimal verbose, 2 debug mode")

# parse the arguments
args = parser.parse_args()

VERBOSE = args.verbose

CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

SMTP_HOST = config.get('SMTP','SMTP_HOST')
SMTP_FROM = config.get('SMTP','SMTP_FROM')
SMTP_TO = config.get('SMTP','SMTP_TO')

BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')
BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_ROOT_PATH = config.get('BACKUP','LOCALBKPATH')

ENCRYPTION_KEYPATH = config.get('ENCRYPT','KEYPATH')


if BACKUP_DEST == 'S3':
    S3_BUCKET = config.get('BACKUP','S3_BUCKET')
    S3_ACCESS_KEY = config.get('BACKUP','S3_ACCESS_KEY')
    S3_SECRET_ACCESS_KEY = config.get('BACKUP','S3_SECRET_ACCESS_KEY')
    S3_DEFAULT_REGION = config.get('BACKUP','S3_DEFAULT_REGION')
elif BACKUP_DEST == 'FTP':
    FTP_SERVER = config.get('BACKUP','FTP_SERVER')
    FTP_USER = config.get('BACKUP','FTP_USER')
    FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
    FTP_ROOT_PATH = config.get('BACKUP','FTP_PATH')
else:
    if VERBOSE >= 1:
        print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
        MESSAGE="""Backup failed
        Bad value in """ +  CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting"
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress", smtphost=SMTP_HOST)
    exit(1)

# Starting process
if VERBOSE >= 1:
    print("")
    print("Starting Wordpress backup process")

# Checking if local backup folders already exists or not. If not, we will create them.
if VERBOSE == 2:
        print("")
        print("Create local backup folders if not existing")
for index in range(int(BACKUP_RETENTION)):
    if index == 0:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
    else:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
    try:
        os.stat(BACKUP_PATH)
    except:
        try:
            os.makedirs(BACKUP_PATH)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(BACKUP_PATH):
                pass

# Check if a backup already occured today
TODAY = time.strftime('%Y%m%d')

DATEFILE = BACKUP_ROOT_PATH + "/" + "DAYJ" + "/" + "date.txt"
try:
    os.stat(DATEFILE)
except:
    BACKUP_ROTATION = False
    if VERBOSE == 2:
        print("ROTATION = False ")
    pass
else:
    # First read content of datefile
    datefile = open(DATEFILE,"r")
    DATEINFILE = datefile.readline()
    # Now compare DATEINFILE with TODAY
    if DATEINFILE == TODAY:
        # Backup already occured today, so no ROTATION needed
        BACKUP_ROTATION = False
        if VERBOSE == 2:
            print("ROTATION = False ")
    else:
        # Local Backup Rotation
        BACKUP_ROTATION = True
        if VERBOSE == 2:
                print("")
                print("Local backup folders rotation")
                print("")

        # Delete DAYJ-RETENTION-1 folder
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(int(BACKUP_RETENTION)-1)
        try:
            if VERBOSE == 2:
                print("Delete of " + BACKUP_PATH)
            shutil.rmtree(BACKUP_PATH, ignore_errors=False, onerror=None)
        except:
            if VERBOSE == 2:
                print("Error during delete of " + BACKUP_PATH)
            MESSAGE="""Backup failed
            Error during delete of """ + BACKUP_PATH
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress", smtphost=SMTP_HOST)
            exit(1)

        # Move content of DAYJ-N to DAYJ-(N+1)
        for index in range(int(BACKUP_RETENTION)-2,-1,-1):
            if index == 0:
                BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ"
                BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-1"
            else:
                BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
                BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-" + str(index+1)
            if VERBOSE == 2:
                print("Rename from " + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO)

            try:
                os.rename(BACKUP_PATH_FROM,BACKUP_PATH_TO)
            except:
                    if VERBOSE == 2:
                        print("Error during rename of " + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO)
                    MESSAGE="""Backup failed
                    Error during rename of """ + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO
                    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
                    exit(1)

        # Create DAYJ folder
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
        if VERBOSE == 2:
                print("Create folder " + BACKUP_PATH )
        os.mkdir(BACKUP_PATH)

BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"

# Part1 : Database backup.
if VERBOSE >=1 :
    print ("")
    print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " " + DB_NAME + " > " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"
try:
    os.system(dumpcmd)
except:
    if VERBOSE == 2:
        print("Error during mysqldump")
    MESSAGE="""Backup failed
    Error during mysqldump"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)

gzipcmd = "gzip -f " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"
try:
    os.system(gzipcmd)
except:
    if VERBOSE == 2:
        print("Error during Gzip of mysqldump")
    MESSAGE="""Backup failed
    Error during Gzip of mysqldump"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)
localMysqlBackup=pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql.gz"

if VERBOSE == 2:
        print("Local MySQL dump copied in " + localMysqlBackup )

if VERBOSE >=1:
    print ("")
    print ("Backup of MySQL completed")

# Part2 : WP Site backup.

if VERBOSE >=1:
    print ("")
    print ("Starting backup of Wordpress Site folder")
# Declare filename
wp_archive = BACKUP_PATH + "/" + "wordpress.site.tar.gz"

# Open file in write mode
try:
    tar = tarfile.open(wp_archive,"w:gz")
    tar.add(WP_PATH)
    tar.close()
except:
    if VERBOSE == 2:
        print("Error during Tar GZ  of Wordpress site")
    MESSAGE="""Backup failed
    Error during Tar GZ of of Wordpress site"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)

if VERBOSE == 2:
        print("Local Wordpress site dump copied in " + wp_archive )

if VERBOSE >= 1:
    print ("")
    print ("Backup of  Wordpress Site folder completed")

# Part 3 : Put datefile in DAYJ
try:
    datefile = open(DATEFILE,"w")
    datefile.write(TODAY)
    datefile.close()
except:
    if VERBOSE == 2:
        print("Error during create of DATEFILE")
    MESSAGE="""Backup failed
    Error during create of DATEFILE"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)


# Part 4 : Encrypt using AES-256
fdKey = open(ENCRYPTION_KEYPATH,'rb')
ENCRYPTION_KEY = fdKey.read()
for file in [localMysqlBackup,wp_archive,DATEFILE]:
    file_name = os.path.basename(file)
    if VERBOSE == 2:
        print("Encrypt file " + file_name)
    try:
        encrypt.encrypt_file(file,ENCRYPTION_KEY)
    except:
        if VERBOSE == 2:
            print("Error during encryption of file " + file_name)
        MESSAGE="""Backup failed
        Error during encryption of file """ + file_name
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)

# Part 5 : Copy to BACKUP_DEST

if BACKUP_DEST == 'S3':
    if VERBOSE >= 1:
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

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id = S3_ACCESS_KEY,
            aws_secret_access_key = S3_SECRET_ACCESS_KEY,
            config = my_config
        )
    except:
        if VERBOSE == 2:
            print("Error during S3 connection")
        MESSAGE="""Backup failed
        Error during S3 connection. Please check your S3 parameters in """ + CONFIG_FILE
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)

    if BACKUP_ROTATION == True:
        # Rotation of backup "folders"
        if VERBOSE == 2:
            print("")
            print ("S3 folders rotation")
        # Delete DAYJ-RETENTION-1 folder
        S3_PATH="DAYJ-" + str(int(BACKUP_RETENTION)-1)
        if VERBOSE == 2:
            print("")
            print("First delete all files in " + S3_PATH    )
        try:
            tools.deleteFolderS3(s3_client,S3_BUCKET,S3_PATH,VERBOSE)
        except:
            if VERBOSE == 2:
                print("Delete files from " + S3_PATH + " failed")
            MESSAGE="""Backup failed
            Error during delete of files from """ + S3_PATH
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)

        if VERBOSE == 2:
            print("")

        # Move content of DAYJ-N to DAYJ-(N+1)
        for index in range(int(BACKUP_RETENTION)-2,-1,-1):
            if index == 0:
                S3_PATH_FROM = "DAYJ"
                S3_PATH_TO = "DAYJ-1"
            else:
                S3_PATH_FROM = "DAYJ-" + str(index)
                S3_PATH_TO = "DAYJ-" + str(index+1)
            if VERBOSE == 2:
                print("Move files from " + S3_PATH_FROM + " to " + S3_PATH_TO)
    #        listObjectFolderS3(s3_client,S3_BUCKET,S3_PATH_FROM,S3_PATH_TO)
            try:
                tools.moveFolderS3(s3_client,S3_BUCKET,S3_PATH_FROM,S3_PATH_TO,VERBOSE)
            except:
                if VERBOSE == 2:
                    print("Move files from " + S3_PATH_FROM + " to " + S3_PATH_TO + " failed")
                MESSAGE="""Backup failed
                Error during move of files from """ + S3_PATH_FROM + " to " + S3_PATH_TO
                tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
                exit(1)

    # Finaly copy new backup files to DAYJ folder
    for file in [localMysqlBackup + ".bin",wp_archive + ".bin",DATEFILE + ".bin"]:
        file_name = os.path.basename(file)
        new_name = "DAYJ/" + file_name
        if VERBOSE == 2:
            print("Transfering file " + file_name + " to " + new_name)
        try:
            s3_client.upload_file(file, S3_BUCKET, new_name)
        except:
            if VERBOSE == 2:
                print("Error during upload of file " + file_name + " in " + new_name)
            MESSAGE="""Backup failed
            Error during upload of file """ + file_name + " in " + new_name
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)

    if VERBOSE >= 1:
        print ("")
        print ("Copy to AWS S3 completed")

else:
    if VERBOSE >= 1:
        print ("")
        print ("Starting Copy to FTP Server")
        print ("")

    ftpserver=tools.connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpserver.cwd(FTP_ROOT_PATH)

    if VERBOSE == 2:
        print ("Init : Create FTP folder if not existing")

    for index in range(int(BACKUP_RETENTION)):
        if index == 0:
            FTP_PATH = "DAYJ"
        else:
            FTP_PATH = "DAYJ-" + str(index)
        if VERBOSE == 2:
            print("Create folder " + FTP_PATH)

        try:
            ftpserver.mkd(FTP_PATH)
        except:
            if VERBOSE == 2:
                print("Error during Create folder of " + BACKUP_PATH + " ie Folder already exist")
            MESSAGE="""Backup failed
            Error during create folder of """ + FTP_PATH + " ie Folder already exist"
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)

    if BACKUP_ROTATION == True:
        # Backup Rotation
        if VERBOSE == 2:
            print("")
            print ("FTP folders rotation")
        # Delete DAYJ-RETENTION-1 folder
        FTP_PATH="DAYJ-" + str(int(BACKUP_RETENTION)-1)
        if VERBOSE == 2:
            print("")
            print("First delete all files in " + FTP_PATH)
        try:
            ftpserver.cwd(FTP_PATH)
        except:
            if VERBOSE == 2:
                print("Error accessing folder " + FTP_PATH + " ie Folder does not exist")
            MESSAGE="""Backup failed
            Error accessing folder """ + FTP_PATH + " ie Folder does not exist"
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)
        try:
            file_list = ftpserver.nlst()
        except:
            if VERBOSE == 2:
                print("Error listing files in folder " + FTP_PATH )
            MESSAGE="""Backup failed
            Error listing files in folder """ + FTP_PATH
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)
        for file in ftpserver.nlst():
            if VERBOSE == 2:
                print("Delete file " + file)
            ftpserver.delete(file)
        ftpserver.cwd("..")
        try:
            if VERBOSE == 2:
                print("Delete folder " + FTP_PATH)
            ftpserver.rmd(FTP_PATH)
        except:
            if VERBOSE == 2:
                print("Error during delete of folder " + FTP_PATH + " ie Folder not empty")
                MESSAGE="""Backup failed
                Error during delete of folder """ + FTP_PATH + " ie Folder not empty"
                tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
                exit(1)

        if VERBOSE == 2:
            print("")

        # Move content of DAYJ-N to DAYJ-(N+1)
        for index in range(int(BACKUP_RETENTION)-2,-1,-1):
            if index == 0:
                FTP_PATH_FROM = "DAYJ"
                FTP_PATH_TO = "DAYJ-1"
            else:
                FTP_PATH_FROM = "DAYJ-" + str(index)
                FTP_PATH_TO = "DAYJ-" + str(index+1)
            if VERBOSE == 2:
                print("Rename from " + FTP_PATH_FROM + " to " + FTP_PATH_TO)
            ftpserver.rename(FTP_PATH_FROM,FTP_PATH_TO)

        # Create DAYJ folder
        FTP_PATH="DAYJ"
        if VERBOSE == 2:
                print("")
                print("Create folder " + FTP_PATH)
                print("")
        ftpserver.mkd(FTP_PATH)

    for file in [localMysqlBackup + ".bin",wp_archive + ".bin",DATEFILE + ".bin"]:
        if VERBOSE >= 1:
            print("Transfering " + file + " to " + FTP_PATH)
        result=tools.uploadftp(ftpserver,file,FTP_PATH)

    tools.closeftp(ftpserver)

    if VERBOSE >= 1:
        print ("")
        print ("Copy to FTP Server completed")



if VERBOSE >= 1:
    print ("")
    print ("Backup script completed")
    print ("Your backups have also been created locally in " + BACKUP_PATH + " directory")

MESSAGE="""Backup script completed
Your backups have also been created locally in """ + BACKUP_PATH + " directory"

tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
