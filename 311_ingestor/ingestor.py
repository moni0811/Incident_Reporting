import random
import requests
import time
import psycopg2
import os
from pathlib import Path

SF_311_API= "https://data.sfgov.org/resource/vw6y-z8j6.json"
CLIENT_URL = "http://client-api-service:80/report"

LIVENESS_FILE = "/tmp/ingestor_live"
READINESS_FILE = "/tmp/ingestor_ready"

def read_secret(path):
    with open(path, "r") as f:
        return f.read().strip()
    
SECRET_PATH = "/etc/secret"

secrets = {
    "DB_HOST": read_secret(f"{SECRET_PATH}/DB_HOST"),
    "DB_NAME": read_secret(f"{SECRET_PATH}/DB_NAME"),
    "DB_USER": read_secret(f"{SECRET_PATH}/DB_USER"),
    "DB_PASSWORD": read_secret(f"{SECRET_PATH}/DB_PASSWORD"),
    "AWS_ACCESS_KEY_ID": read_secret(f"{SECRET_PATH}/AWS_ACCESS_KEY_ID"),
    "AWS_SECRET_ACCESS_KEY": read_secret(f"{SECRET_PATH}/AWS_SECRET_ACCESS_KEY")
}

def touch_file(path):
    Path(path).touch()

def get_311_data_and_process():
    print("311 data processing")

    offset=0
    while True:
        try:
            touch_file(READINESS_FILE)
            params = {
                "$limit": 10,
                "$offset": offset,
                "$order": "service_request_id DESC"}
            
            #responses=requests.get(SF_311_API, params={"service_request_id": 13439477})
            responses=requests.get(SF_311_API, params=params)
            json_responses=responses.json()
            if not json_responses:
                print("No more data to process. Exiting.")
                break
            
            conn = psycopg2.connect(
                host=secrets["DB_HOST"],
                database=secrets["DB_NAME"],
                user=secrets["DB_USER"],
                password=secrets["DB_PASSWORD"]
                )
            cur = conn.cursor()

            touch_file(READINESS_FILE)
            
            for issue in json_responses:
                incident_id=str(issue.get("service_request_id"))

                
                cur.execute("""
                    SELECT count(1) from incidents where incident_id=%s LIMIT 1
                 """,(incident_id,))
                exists = cur.fetchone()

                if exists and exists[0] > 0:
                    print(f"Incident {incident_id} already exists in the database. Skipping.")
                    continue
                    
                description= (
                    f"service_name: {issue.get('service_name') or ''} " 
                    f"service_subtype: {issue.get('service_subtype') or ''} "
                    f"service_details: {issue.get('service_details') or ''}"
                )

                address = issue.get("address", "")
                print("address : ", address)

                media_data=issue.get("media_url")
                print('media_data:', media_data)
                if media_data and isinstance(media_data, dict):
                    image_url = media_data.get("url")
                else:
                    image_url = media_data
                print('image_url:', image_url)
                # if image_url:
                #     local_image=f"{incident_id}.jpg"
                #     with requests.get(image_url, stream=True) as r:
                #         r.raise_for_status()
                #         with open(local_image,'wb') as file_image:
                #             for i in r.iter_content(chunk_size=8192):
                #                 file_image.write(i)
                #     print('Image downloaded')
                #     import boto3
                #     bucket_name="s3-incident-report-bucket"
                #     s3_client=boto3.client("s3",
                #                             aws_access_key_id=secrets["AWS_ACCESS_KEY_ID"],
                #                             aws_secret_access_key=secrets["AWS_SECRET_ACCESS_KEY"])
                #     s3_client.upload_file(
                #         Filename=local_image,  # Path to the file on your computer
                #         Bucket=bucket_name, 
                #         Key=local_image,       # Name it will have in S3
                #         ExtraArgs={
                #             'ContentType': 'image/jpeg' 
                #         },
                #     )
                #     s3_url=f"https://{bucket_name}.s3.amazonaws.com/{local_image}"
                #     print('Image s3_url:', s3_url)
                json_data = {
                    "incident_id": incident_id,
                    "description": description,
                    "address": address,
                    "image_url": image_url if image_url else None
                }
            print('json_data:',json_data)
            result=requests.post(CLIENT_URL,json=json_data)

            cur.close()
            conn.close()
            
            touch_file(LIVENESS_FILE)
            offset+=10
            sleep_time = 18000

            print(f"⏳ Sleeping {sleep_time}s...")
            time.sleep(sleep_time)

        except Exception as e:
            if os.path.exists(READINESS_FILE):
                os.remove(READINESS_FILE)
            print(f"Error : {e}")
            time.sleep(100)

if __name__ == "__main__":
    get_311_data_and_process()
