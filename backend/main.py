from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import redis
import json
from celery_app import celery_app, classify_image_task

app = FastAPI(title="Image Classification API")

# Redis connection for task status
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=6379,
    db=0,
    decode_responses=True
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Image Classification API"}

@app.post("/classify")
async def classify_image(file: UploadFile = File(...)):
    """
    Accepts an image upload and queues it for classification.
    Returns a task ID that can be used to check status and retrieve results.
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Enqueue the classification task
        celery_task = classify_image_task.delay(image_data, task_id)
        
        # Store initial status
        redis_client.setex(
            f"task:{task_id}:status",
            3600,  # 1 hour expiry
            "queued"
        )
        redis_client.setex(
            f"task:{task_id}:celery_id",
            3600,
            celery_task.id
        )
        
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Image queued for classification"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/task/{task_id}/status")
def get_task_status(task_id: str):
    """
    Get the status of a classification task.
    Returns: queued, processing, completed, or failed
    """
    status = redis_client.get(f"task:{task_id}:status")
    
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    response = {"task_id": task_id, "status": status}
    
    # If completed, include results
    if status == "completed":
        results_json = redis_client.get(f"task:{task_id}:results")
        if results_json:
            response["results"] = json.loads(results_json)
    
    # If failed, include error information
    if status == "failed":
        error_json = redis_client.get(f"task:{task_id}:error")
        if error_json:
            error_info = json.loads(error_json)
            response["error"] = error_info.get("error", "Unknown error")
            # Don't expose full traceback to client, just the error message
    
    return response

@app.post("/task/{task_id}/retry")
async def retry_task(task_id: str, file: UploadFile = File(...)):
    """
    Retry a failed classification task.
    Requires uploading the image again.
    """
    try:
        # Check if task exists and is in failed state
        status = redis_client.get(f"task:{task_id}:status")
        if not status:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if status != "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry task with status: {status}"
            )
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Get celery task ID
        celery_id = redis_client.get(f"task:{task_id}:celery_id")
        
        # Enqueue new classification task with same task_id
        celery_task = classify_image_task.delay(image_data, task_id)
        
        # Update status
        redis_client.setex(
            f"task:{task_id}:status",
            3600,
            "queued"
        )
        redis_client.setex(
            f"task:{task_id}:celery_id",
            3600,
            celery_task.id
        )
        
        # Clear previous error
        redis_client.delete(f"task:{task_id}:error")
        
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Task requeued for classification"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrying task: {str(e)}")
