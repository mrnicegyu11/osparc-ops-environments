# SFTP Stack

Stack to deploy a SFTP server.

# Use case

This SFTP server gives access to folders present on the leader node of the swarm (the one from which the swarm launch the tasks). Some client nodes can then access to theses folders with a SFTP client. This allows us to spwan services which are using docker volumes with a bind mount to the local ops git repo on another node than the leader node. 