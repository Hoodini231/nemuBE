
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
from app.routers import n8n_processor
import json
from fastapi import Request
import base64
from io import BytesIO
from PIL import Image

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
        # Leverage kumiko locally
        kumiko_path = os.path.abspath("/Users/shaun/Documents/kumiko/kumiko") 
        # Execute the kumiko command to subdivide the panels
        command = ["python3", kumiko_path, "-i", "test.png", "--save-panels"]
        result = subprocess.run(command, capture_output=True, text=True)

        # Check for errors
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error: {result.stderr}")
        
        # Parse the JSON output
        output_json = json.loads(result.stdout)

        # Grab all files in the output directory
        output_dir = os.path.join(os.path.dirname(kumiko_path), "out", "panels")
        if not os.path.exists(output_dir):
            raise HTTPException(status_code=500, detail="Output directory does not exist")

        panels_generated = os.listdir(output_dir)
        panels = [panel for panel in panels_generated if os.path.isfile(os.path.join(output_dir, panel))]
        panels.sort()  # Ensure consistent order

        

        # Extract relevant information for panel sizing and positions
        size = output_json[0]['size']
        panelData = output_json[0]['panels']

        # Push the panels onto blank canvases to integrate with imageMagick psd later
        for i in range(0, len(panels)):
            command = ["magick", os.path.join(output_dir, panels[i]), f"panel{i}.png"]
            result = subprocess.run(command, capture_output=True, text=True)
              # Ensure the file is written before proceeding
            command = ["magick", "-size", f"{size[0]}x{size[1]}", "canvas:none", "-compose", "over", f"panel{i}.png", "-geometry", f"+{panelData[i][0]}+{panelData[i][1]}", "-composite", f"formatted_panel{i}.png"]
            result = subprocess.run(command, capture_output=True, text=True)
        
        # potentially run our segmentation model here?

        # aggregate into .psd file for modularity
        print ("Creating PSD file with panels:", panels)
        psd_command = (
            "magick " +
            " ".join([f"formatted_panel{i}.png" for i in range(len(panels))]) +
            " \( -clone 0,1 -flatten \) -insert 0 output_psd.psd"
        )

        # Execute the PSD creation command
        result = subprocess.run(psd_command, shell=True, capture_output=True, text=True)

        # Check for errors in the PSD creation command
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"PSD Creation Error: {result.stderr}")
        
        # magick testBg.jpg king.png \( -clone 0,1 -flatten \) -insert 0 output_psd.psd


        return {"message": "Image processed and PSD created successfully", "size": size, "panels": panels}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse JSON output from kumiko.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
