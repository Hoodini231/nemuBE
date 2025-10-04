from time import time
from venv import logger
from fastapi import FastAPI, UploadFile, HTTPException, File
import subprocess
import os
import json
from fastapi import Request
import base64
from io import BytesIO
from PIL import Image

app = FastAPI()

@app.post("/process-image")
async def process_image(request: Request, file: UploadFile = File(...)):
    try:    
        # Save the uploaded file as binary
        file_location = "uploaded_image.png"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Read the request body
        request = await request.json()

        # Extract base64 images from the request body
        if "images" not in request or not isinstance(request["images"], list):
            raise HTTPException(status_code=400, detail="Invalid request format. 'images' field is required and must be a list.")

        images = []
        for idx, image_data in enumerate(request["images"]):
            try:
                # Decode the base64 image
                image_bytes = base64.b64decode(image_data)
                image = Image.open(BytesIO(image_bytes))
                image_path = f"image_{idx}.png"
                image.save(image_path)
                images.append(image_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process image {idx}: {str(e)}")
            
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
        size = None
        panelData = None
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
