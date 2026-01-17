from celery import Celery
import os
import numpy as np
from PIL import Image
import tensorflow as tf
import redis
import json
import traceback
from io import BytesIO

# Redis connection for storing task results
redis_client = redis.Redis(host=os.getenv('REDIS_HOST', 'redis'), port=6379, db=0, decode_responses=True)

# Celery app configuration
celery_app = Celery(
    'classification_worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
)

@celery_app.task(bind=True, name='classify_image_task')
def classify_image_task(self, image_data: bytes, task_id: str):
    """
    Classify an image using TensorFlow Lite model.
    This runs in a separate worker process.
    """
    try:
        # Update task status to processing
        redis_client.setex(
            f"task:{task_id}:status",
            3600,  # 1 hour expiry
            "processing"
        )
        
        # Load the TFLite model
        model_path = os.getenv('MODEL_PATH', 'classification_model/mobilenet_v1_1.0_224_quant.tflite')
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        
        # Get input and output tensors
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # Process the image
        image = Image.open(BytesIO(image_data))
        res_im = image.resize((224, 224))
        np_res_im = np.array(res_im)
        np_res_im = np_res_im.astype('uint8')
        
        if len(np_res_im.shape) == 3:
            np_res_im = np.expand_dims(np_res_im, 0)
        
        # Run inference
        interpreter.set_tensor(input_details[0]['index'], np_res_im)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        
        # Process results
        classification_prob = []
        classification_label = []
        total = 0
        
        for index, prob in enumerate(output_data[0]):
            if prob != 0:
                classification_prob.append(prob)
                total += prob
                classification_label.append(index)
        
        # Load labels
        labels_path = os.getenv('LABELS_PATH', 'classification_model/labels_mobilenet_quant_v1_224.txt')
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels file not found: {labels_path}")
        
        with open(labels_path, 'r') as f:
            label_names = [line.rstrip('\n') for line in f]
        
        found_labels = np.array(label_names)[classification_label]
        
        # Calculate probabilities and pair with labels
        probabilities = classification_prob / total if total > 0 else classification_prob
        label_prob_pairs = list(zip(found_labels, probabilities))
        
        # Sort by probability in descending order
        sorted_pairs = sorted(label_prob_pairs, key=lambda x: x[1], reverse=True)
        
        # Format results
        results = [
            {"label": label, "probability": float(prob)}
            for label, prob in sorted_pairs
        ]
        
        # Store results in Redis
        redis_client.setex(
            f"task:{task_id}:results",
            3600,  # 1 hour expiry
            json.dumps(results)
        )
        
        # Update status to completed
        redis_client.setex(
            f"task:{task_id}:status",
            3600,
            "completed"
        )
        
        return {"status": "completed", "results": results}
        
    except Exception as e:
        # Store error information
        error_info = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        
        redis_client.setex(
            f"task:{task_id}:error",
            3600,
            json.dumps(error_info)
        )
        
        redis_client.setex(
            f"task:{task_id}:status",
            3600,
            "failed"
        )
        
        # Re-raise to mark task as failed in Celery
        raise
