import base64
import os

def encode_image_to_base64(image_path):
    """
    Encodes an image to a base64 string.

    :param image_path: Path to the image file
    :return: Base64 encoded string of the image
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"The file {image_path} does not exist.")
    
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string

def save_image_bytes(image_path, output_path):
    """
    Saves the bytes of an image file to a specified output file.

    :param image_path: Path to the image file
    :param output_path: Path to the output file where image bytes will be saved
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"The file {image_path} does not exist.")
    
    # Read the image file as binary
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    # Save the binary data to a file
    with open(output_path, "wb") as output_file:
        output_file.write(image_bytes)

    print(f"Image bytes saved to {output_path}")

def main():
    # Example usage
    image_path = input("Enter the path to the image: ")
    output_path = "image_bytes.bin"  # Default output file
    try:
        # Encode image to base64
        encoded_image = encode_image_to_base64(image_path)
        print("Base64 Encoded Image:")
        print(encoded_image)
        
        # Save image bytes to file
        save_image_bytes(image_path, output_path)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()