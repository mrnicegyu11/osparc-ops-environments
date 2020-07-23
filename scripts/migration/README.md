# Summary

Theses scripts allows you to :
- Easily backup and restore a PGSQL database for the Simcore stack.
- Easily copy the data (from a s3/minio bucket to another s3/minio bucket) from the simcore stack.


## Database backup and restore

The backup script create a backup of the database in the /tmp folder. The restore script will delete the database in the destination server, create a new empty one, add the grafanareader user and restore the database. Finally, it will delete the temporary database created in /tmp/
### How to proceed
- Update the .env file with the necessary informations. The variables containing ORIGIN are for the host you want to backup the data.
Don't forget to fill the POSTGRES_GRAFANA_PASSWORD. This variable will be used to create a grafanareader ROLE.

- Execute db-backup.bash 
```
./db-backup.bash 
```


- Execute db-restore.bash
```
./db-restore.bash
```

## S3 migration

The S3 migration scripts connect to the origin and destination hosts, and copy the data of the desired bucked from the origin to the destination.

### How to proceed
- Update the .env file with the necessary informations.
- Execute ./s3-data-migration.bash to migrate the data or/and ./s3-registry-migration.bash to migrate the registry data.
```
./s3-data-migration.bash
```
and/or
```
./s3-registry-migration.bash
```