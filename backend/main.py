from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="Image Classification API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Image Classification API"}

@app.post("/classify")
async def classify_image(file: UploadFile = File(...)):
    # TODO: Implement image image recognition logic
    results_file = "results.txt"
    
    if not os.path.exists(results_file):
        return JSONResponse(
            status_code=404,
            content={"error": "Results file not found"}
        )
    
    # Read and parse results.txt
    results = []
    with open(results_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                parts = line.split("\t")
                if len(parts) == 2:
                    label, probability = parts
                    results.append({
                        "label": label,
                        "probability": float(probability)
                    })
    
    return {
        "results": results
    }
