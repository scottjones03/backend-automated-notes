
import os
import queue
from gpt4_api import GPT4API
from notionAPI import NotionAPI
import time
import queue
from pdfid.pdfid import PDFiD
from concurrent.futures import ThreadPoolExecutor
import os
import json
import xml.etree.ElementTree as ET
from azurecloud import AzureBlobStorageManager

def is_pdf_safe(pdf_path):
    """Run PDFiD on the PDF and check the output for signs of exploits."""
    xmlcontent = PDFiD(pdf_path)

    # Parse the XML content into an ElementTree
    root = ET.fromstring(xmlcontent.toxml())

    # Search for 'JS' and 'JavaScript' tags
    js_elements = root.findall('.//JS')
    javascript_elements = root.findall('.//JavaScript')

    # Then check counts
    if len(js_elements) > 0 or len(javascript_elements) > 0:
        return False

    return True




NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
SESSION_PATH = os.environ.get("SESSION_TOKEN")



def run_pdf_tasks(jobsqueue: queue.Queue):
    while True:
        try:
            AzureBlobStorageManager.update_jobs(jobs)
            if jobsqueue.empty():
                
                time.sleep(30)
                continue
            blob_job_name, item = jobsqueue.get()  # This will block until an item is available
            prompts = item[5]
            if item is None:  # We use 'None' as a signal to stop
                time.sleep(30)
                continue

            with ThreadPoolExecutor(max_workers=1) as executor:
                if item[4]==gpt4api._model:
                    future = executor.submit(gpt4api.parsePDF, item[0], item[1], prompts, item[2])
                else:
                    oldgpt4api = gpt4api
                    future1 = executor.submit(oldgpt4api.safe_close)
                    future1.result(timeout=360)
                    gpt4api = GPT4API(token, notionapi, model=item[4])
                    future = executor.submit(gpt4api.parsePDF, item[0], item[1], prompts, item[2])
                future.result(timeout=7200)  # 2 hours timeout for the task to complete
            jobsqueue.task_done()
            AzureBlobStorageManager.delete_blob(item[0], blob_job_name)
            
            
        except Exception as e:
         
            print(f'Task took too long to complete. Restarting the task for item: {item} exception: {e}')
            jobsqueue.put(item)  # Putting the item back in queue to retry
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    oldgpt4api = gpt4api
                    future1 = executor.submit(oldgpt4api.safe_close)
                    future1.result(timeout=360)
            except Exception as e:
                print(f"failed to delete old api objects {e}")
            while True:
                try:
                    notionapi = NotionAPI(NOTION_TOKEN)
                    with open(SESSION_PATH, 'r') as f:
                        token = f.read()
                    gpt4api = GPT4API(token, notionapi, model=item[4])
                    break
                except Exception as e:
                    print(f"failed to relaunch apis{e}" )
                
def convert_string_to_json(string_data):
   

    # Replace the HTML-encoded single quotes with double quotes
    string_data = string_data.replace("&#39;", '"')

    # Convert the string to a JSON object
    json_data = json.loads(string_data)

    return json_data  

    
def refresh_queue(jobs):
    import requests
    try: 
        url = "http://172.28.193.110:80/json_files"  # Replace <website-url> with the actual URL of the Flask app

        response = requests.get(url)
        if response.status_code == 200:
            json_files = str(response.content).split('Data:</strong> ')[1].split('<br>')[0]
            saved_jobs = []
            for j in jobs.queue:
                saved_jobs.append(j[0])
            
            with open('./localjobs/localjobs.json', 'rb') as f:
                saved_queue = json.load(f)
                for item in saved_queue:
                    saved_jobs.append(item[0])
            json_file = convert_string_to_json(json_files)
            for item in json_file:
                if item[0] in saved_jobs :
                    continue
                else:
                    jobs.put(item)
                    saved_jobs.append(item[0])
        else:
            print("Failed to retrieve JSON files list")
    except Exception as e:
        print(f"Failed to retrieve JSON files list {e}")


if __name__ == "__main__":
    jobs = queue.Queue()
    
    
    while True:
        try:
            run_pdf_tasks(jobs)
        except Exception as e:
            print(e)
        