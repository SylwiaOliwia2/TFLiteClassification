from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
import uuid
import redis
import json
import asyncio
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
        redis_client.publish(
            f"task:{task_id}:updates",
            json.dumps({"task_id": task_id, "status": "queued"})
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

@app.get("/task/{task_id}/stream")
async def stream_task_status(task_id: str):
    """
    Server-Sent Events (SSE) stream for real-time task status updates.
    Pushes updates when task status changes.
    """
    async def event_generator():
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        channel = f"task:{task_id}:updates"
        
        try:
            pubsub.subscribe(channel)
            
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None,
                lambda: redis_client.get(f"task:{task_id}:status")
            )
            
            if status:
                initial_data = {"task_id": task_id, "status": status}
                if status == "completed":
                    results_json = await loop.run_in_executor(
                        None,
                        lambda: redis_client.get(f"task:{task_id}:results")
                    )
                    if results_json:
                        initial_data["results"] = json.loads(results_json)
                elif status == "failed":
                    error_json = await loop.run_in_executor(
                        None,
                        lambda: redis_client.get(f"task:{task_id}:error")
                    )
                    if error_json:
                        error_info = json.loads(error_json)
                        initial_data["error"] = error_info.get("error", "Unknown error")
                
                yield f"data: {json.dumps(initial_data)}\n\n"
                
                if status in ["completed", "failed"]:
                    return
            
            while True:
                try:
                    # Run blocking Redis calls in thread pool
                    loop = asyncio.get_event_loop()
                    message = await loop.run_in_executor(
                        None, 
                        lambda: pubsub.get_message(timeout=1.0)
                    )
                    
                    if message and message['type'] == 'message':
                        data = json.loads(message['data'])
                        yield f"data: {json.dumps(data)}\n\n"
                        
                        # Close stream if task is done
                        if data.get('status') in ['completed', 'failed']:
                            break
                    
                    # Also check Redis directly in case we missed the pubsub message
                    current_status = await loop.run_in_executor(
                        None,
                        lambda: redis_client.get(f"task:{task_id}:status")
                    )
                    if current_status and current_status in ["completed", "failed"]:
                        # Get final data
                        final_data = {"task_id": task_id, "status": current_status}
                        if current_status == "completed":
                            results_json = await loop.run_in_executor(
                                None,
                                lambda: redis_client.get(f"task:{task_id}:results")
                            )
                            if results_json:
                                final_data["results"] = json.loads(results_json)
                        elif current_status == "failed":
                            error_json = await loop.run_in_executor(
                                None,
                                lambda: redis_client.get(f"task:{task_id}:error")
                            )
                            if error_json:
                                error_info = json.loads(error_json)
                                final_data["error"] = error_info.get("error", "Unknown error")
                        
                        yield f"data: {json.dumps(final_data)}\n\n"
                        break
                    
                    # Small delay to prevent tight loop
                    await asyncio.sleep(0.1)
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break
                    
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

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
        
        # Enqueue new classification task with same task_id
        celery_task = classify_image_task.delay(image_data, task_id)
        
        # Update status
        redis_client.setex(
            f"task:{task_id}:status",
            3600,
            "queued"
        )
        # Publish queued status
        redis_client.publish(
            f"task:{task_id}:updates",
            json.dumps({"task_id": task_id, "status": "queued"})
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
