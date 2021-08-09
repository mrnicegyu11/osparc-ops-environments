# Goal

This script use [the s3-pit-restore script](https://github.com/angeloc/s3-pit-restore) with a little wrapper to ensure that it can be used with minio.

# Usage

## Listing versions
* Create an .env file from the template.env file and fill it

- First, you need to list the versions of what need to be restored. In the .env file, you can fill the $OBJECT_PATH variable - which correspond to the full path of the object (or folder) you want to restore. E.G
```console
OBJECT_PATH="production-simcore/e6b05708-c169-11eb-b3e2-02420a0b009a/463df499-8691-42cd-9b03-e465fc264cf4/"
```

- Next, you can list the versions executing
```console 
./historic_bucket.bash
```

The versions will appear in UTC + 0. You need to add two hours to have a Zurich corresponding timeline.(But don't add them while using the hours in restoring part)

- A list of the different versions appears. Find the creation datetime of the version you wish to restore. Add one second to it to be sure that the correct version will be restored. It can be any datetime between the version you need and the next one, NOT including the creation of the version you want to restore.

## Restoring

* You can launch the restoration script with 
```console
./launch.bash command
```
where command is the command you would use with s3-pit-restore.

E.g 1 :
If you want to restore the bucket simcore-origin to his  06-17-2021 23:59:50 UTC version in the bucket simcore-new-bucket, using the endpoint https://storage.osparc.speag.com : 
```console
sudo ./launch.bash --bucket simcore-origin --dest-bucket simcore-new-bucket 06-17-2021 23:59:50 UTC "06-17-2021 23:59:50 +2" u https://storage.osparc.speag.com
```
E.g 2 : if you want to restore the bucket production-simcore to his  06-17-2021 23:59:50 version in a local path (/tmp/test), using the endpoint https://storage.osparc.speag.com : 

```console
sudo ./launch.bash --bucket production-simcore --dest /tmp/test  -p e6b05708-c169-11eb-b3e2-02420a0b009a/463df499-8691-42cd-9b03-e465fc264cf4/work.zip -t "07-05-2021 00:58:48 UTC" -u https://storage.osparc.speag.com
```