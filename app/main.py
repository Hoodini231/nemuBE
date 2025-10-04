from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
from app.routers import n8n_processor

app = FastAPI()

# CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(n8n_processor.router, prefix="/api", tags=["n8n"])

@app.get("/process-image")
async def process_image():
    try:
        kumiko_path = os.path.abspath("/Users/shaun/Documents/kumiko/kumiko") 
        # Execute the kumiko command
        command = ["python3", kumiko_path, "-i", "test.png", "--save-panels"]
        result = subprocess.run(command, capture_output=True, text=True)

        # Check for errors
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error: {result.stderr}")
        
        # Grab all files in the output directory
        output_dir = os.path.join(os.path.dirname(kumiko_path), "out", "panels")
        if not os.path.exists(output_dir):
            raise HTTPException(status_code=500, detail="Output directory does not exist")

        files = os.listdir(output_dir)
        files = [file for file in files if os.path.isfile(os.path.join(output_dir, file))]

        return {"message": "Image processed successfully", "output": len(files)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
