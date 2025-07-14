import streamlit as st
import pytesseract
from PIL import Image
from openai import OpenAI
import re
import os
from io import BytesIO
import requests
import time
import pandas as pd


# Ensure Tesseract OCR is configured correctly
possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    ]
for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break


# Configure the page
st.set_page_config(
    page_title="Menu to Images Generator",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Menu to Images Generator")
st.markdown("Upload a menu image and I'll generate pictures of the dishes!")

# Sidebar for API configuration
st.sidebar.header("⚙️ Configuration")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", help="Enter your OpenAI API key")

# Initialize OpenAI client
client = None
if openai_api_key:
    client = OpenAI(api_key=openai_api_key)

# File upload
uploaded_file = st.file_uploader(
    "Choose a menu image",
    type=['png', 'jpg', 'jpeg'],
    help="Upload a clear image of a menu"
)

def extract_text_from_image(image):
    """Extract text from image using Tesseract OCR"""
    try:
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error extracting text: {str(e)}")
        st.error("Tesseract OCR not found. Please install Tesseract or use Google Cloud Vision API instead.")
        st.markdown("""
        **To fix this:**
        1. **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
        2. **Mac**: Run `brew install tesseract`
        3. **Linux**: Run `sudo apt-get install tesseract-ocr`
        
        Or contact me to switch to Google Cloud Vision API.
        """)
        return ""

def parse_menu_items(text):
    """Parse menu text to extract dish names and descriptions"""
    lines = text.split('\n')
    menu_items = []
    
    current_item = ""
    current_description = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip obvious non-food items (prices, headers, etc.)
        if re.match(r'^[\d\$\£\€\¥]+', line) or len(line) < 3:
            continue
            
        # Check if line looks like a dish name (often shorter, may have price at end)
        if len(line) < 50 and (re.search(r'\$\d+', line) or line.isupper() or line.istitle()):
            if current_item:
                menu_items.append({
                    'name': current_item,
                    'description': current_description
                })
            current_item = re.sub(r'\$[\d.]+', '', line).strip()
            current_description = ""
        else:
            # This looks like a description
            current_description += " " + line
    
    # Add the last item
    if current_item:
        menu_items.append({
            'name': current_item,
            'description': current_description.strip()
        })
    
    return menu_items

def generate_food_image(dish_name, description=""):
    """Generate an image of a food dish using OpenAI's DALL-E"""
    if not client:
        st.warning("Please enter your OpenAI API key in the sidebar")
        return None
    
    try:
        # Create a descriptive prompt
        prompt = f"A high-quality, appetizing photo of {dish_name}"
        if description:
            prompt += f", {description[:100]}"  # Limit description length
        prompt += ", professional food photography, well-lit, restaurant quality"
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        
        # Download the image
        img_response = requests.get(image_url)
        img = Image.open(BytesIO(img_response.content))
        
        return img
        
    except Exception as e:
        st.error(f"Error generating image for {dish_name}: {str(e)}")
        return None

# Main app logic
if uploaded_file is not None:
    # Display uploaded image
    image = Image.open(uploaded_file)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Uploaded Menu")
        st.image(image, caption="Uploaded Menu", use_column_width=True)
    
    with col2:
        st.subheader("🔍 Processing...")
        
        # Extract text
        with st.spinner("Extracting text from image..."):
            extracted_text = extract_text_from_image(image)
        
        if extracted_text:
            st.success("Text extracted successfully!")
            
            # Show extracted text in an expander
            with st.expander("View Extracted Text"):
                st.text_area("Raw Text", extracted_text, height=200)
            
            # Parse menu items
            menu_items = parse_menu_items(extracted_text)
            
            if menu_items:
                st.subheader(f"🍽️ Found {len(menu_items)} Menu Items")
                
                # Display menu items and generate images
                for i, item in enumerate(menu_items):
                    st.markdown(f"### {item['name']}")
                    if item['description']:
                        st.write(f"*{item['description'][:200]}...*" if len(item['description']) > 200 else f"*{item['description']}*")
                    
                    # Generate image button
                    if st.button(f"Generate Image for {item['name']}", key=f"gen_{i}"):
                        if client:
                            with st.spinner(f"Generating image for {item['name']}..."):
                                generated_image = generate_food_image(item['name'], item['description'])
                                if generated_image:
                                    st.image(generated_image, caption=f"Generated: {item['name']}", width=300)
                        else:
                            st.warning("Please enter your OpenAI API key to generate images")
                    
                    st.divider()
                
                # Bulk generation option
                if client:
                    st.subheader("🚀 Bulk Generation")
                    if st.button("Generate All Images", type="primary"):
                        progress_bar = st.progress(0)
                        
                        for i, item in enumerate(menu_items):
                            with st.spinner(f"Generating {i+1}/{len(menu_items)}: {item['name']}"):
                                generated_image = generate_food_image(item['name'], item['description'])
                                if generated_image:
                                    st.image(generated_image, caption=f"Generated: {item['name']}", width=300)
                                
                                # Update progress
                                progress_bar.progress((i + 1) / len(menu_items))
                                
                                # Small delay to avoid rate limiting
                                time.sleep(1)
                        
                        st.success("All images generated!")
            
            else:
                st.warning("No menu items could be identified. Try uploading a clearer image.")
        
        else:
            st.error("Could not extract text from the image. Make sure the image is clear and contains readable text.")

# Instructions
st.sidebar.markdown("""
## 📋 Instructions

1. **Get OpenAI API Key**: Visit [OpenAI](https://openai.com/api/) to get your API key
2. **Upload Menu**: Choose a clear image of a menu
3. **Review Items**: Check the extracted menu items
4. **Generate Images**: Click to generate images for individual items or all at once

## 🔧 Requirements

Make sure you have installed:
```bash
pip install streamlit pytesseract pillow openai requests
```

For Tesseract OCR, you may need to install it separately:
- **Windows**: Download from GitHub releases
- **Mac**: `brew install tesseract`
- **Linux**: `sudo apt-get install tesseract-ocr`
""")

st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ using Streamlit")