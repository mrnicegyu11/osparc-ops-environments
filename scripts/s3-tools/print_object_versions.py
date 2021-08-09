import typer
import os
import datetime


def list_versions(object_path, s3_access_key_id, s3_secret_access_key, s3_endpoint):

    stream = os.popen('docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://'+s3_access_key_id+':'+s3_secret_access_key+'@'+s3_endpoint+'" \
minio/mc ls --versions local/'+object_path)
    output = stream.read()
    #print(output)
    lines_output = output.split('\n')
    for i, line in enumerate(lines_output):
        if line != "":
            substrings = line.split()
            date_object = datetime.datetime.strptime(substrings[0][1:]+":"+substrings[1], "%Y-%m-%d:%H:%M:%S")
            # We add two hours to be in the Zurich time
            date_object =  date_object + datetime.timedelta(hours=2)
            #print(date_object)
            substrings[0] = date_object
            lines_output[i] = substrings[0].strftime("%m/%d/%Y %H:%M:%S") + " " + substrings[3] + " " + substrings[4] + " " + substrings[5] + " " + substrings[6] + " " + substrings[7]
        print(lines_output[i])






def main(s3_access_key_id: str, s3_secret_access_key: str, s3_endpoint: str, object_path: str = typer.Argument(..., help="Direct path to the object you are looking for. eg production-simcore/9febbfe0-df2f-11eb-b30d-02420a0b00b9/d496a0d9-12ff-4afd-a49b-2c94f9490860/")):
    list_versions(object_path, s3_access_key_id, s3_secret_access_key, s3_endpoint)
 

if __name__ == "__main__":
    typer.run(main)