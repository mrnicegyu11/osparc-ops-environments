#!/bin/bash
#
# Create and restore docker volumes
#

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

source .env

backup()
{
    IFS=', ' read -r -a volumes <<< "${SOURCE_VOLUMES_NAME}"
    IFS=', ' read -r -a folders <<< "${SOURCE_FOLDERS_NAME}"
	count=0
	for element in "${volumes[@]}" 
	do 
        echo "Macking a backup of ${element}:${folders[$count]}"
        docker run --rm  -v /tmp/backup/:/backup -v ${element}:${folders[$count]} ubuntu tar cvf /backup/${element}.tar ${folders[$count]}
        echo "Backup available : /tmp/backup/${element}.tar"
	    count=$((count+1))
	done
    exit 0
}

transfer()
{
    sudo apt install sshpass;
    for entry in /tmp/backup/*
    do
        echo "Sending $entry to ${SSH_HOST}"
        sshpass -p $SSH_PWD scp $entry ${SSH_USER}@${SSH_HOST}:/tmp/backup
    done
    exit 0
}

restore()
{
    IFS=', ' read -r -a volumes <<< "${DEST_VOLUMES_NAME}"
	count=0
	for element in "${volumes[@]}"
    do
        echo "Deleting volume ${element}"
        docker volume rm -f ${element}
        echo "Creating a new empty volume"
        docker volume create ${element}
        echo "Restoring the volume..."
        docker run --rm -v /tmp/backup/:/backup -v ${element}:${DEST_FOLDER_NAME} ubuntu bash -c "cd ${DEST_FOLDER_NAME} && tar xvf /backup/${SOURCE_VOLUME_NAME}.tar --strip 1 && cd .. && chmod -R 777 ${DEST_FOLDER_NAME}"
        echo "Volume restored."
    done

    read -p "CAUTION ! This script will remove the existing volume if it exists before restoring it. Are you sure ? (y/n)? " answer
    case ${answer:0:1} in
        y|Y )
            echo "Deleting volume ${DEST_VOLUME_NAME}"
            docker volume rm -f ${DEST_VOLUME_NAME}
            echo "Creating a new empty volume"
            docker volume create ${DEST_VOLUME_NAME}
            echo "Restoring the volume..."
            docker run --rm -v /tmp/backup/:/backup -v ${DEST_VOLUME_NAME}:${DEST_FOLDER_NAME} ubuntu bash -c "cd ${DEST_FOLDER_NAME} && tar xvf /backup/${SOURCE_VOLUME_NAME}.tar --strip 1 && cd .. && chmod -R 777 ${DEST_FOLDER_NAME}"
            echo "Volume restored."
        ;;
        * )
            echo "Prudence est mère de sureté "
        ;;
    esac
    exit 0
}

backup_and_restore_ssh()
{
    read -p "CAUTION ! This script will remove the existing volume if it exists before restoring it. Are you sure ? (y/n)? " answer
    case ${answer:0:1} in
        y|Y )
            echo "Deleting volume ${DEST_VOLUME_NAME}"
            docker volume rm -f ${DEST_VOLUME_NAME}
            echo "Creating a new empty volume"
            docker volume create ${DEST_VOLUME_NAME}
            echo "Macking a backup of ${SOURCE_VOLUME_NAME} in the distant host $SSH_HOST"
            ssh $SSH_HOST \
            "docker run --rm -v ${SOURCE_VOLUME_NAME}:${SOURCE_FOLDER_NAME} alpine ash -c 'cd ${SOURCE_FOLDER_NAME} ; tar -cf - . '" \
            | \
            docker run --rm -i -v "${DEST_VOLUME_NAME}":"${DEST_FOLDER_NAME}" alpine ash -c "cd ${DEST_FOLDER_NAME} ; tar -xpvf - ; "
            echo "Volume restored."
        ;;
        * )
            echo "Prudence est mère de sureté "
        ;;
    esac
    exit 0

}

[ $1 = "backup" ] && backup
[ $1 = "restore" ] && restore
[ $1 = "transfer" ] && transfer
[ $1 = "backup_and_restore_ssh" ] && backup_and_restore_ssh