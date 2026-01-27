import asyncio
import os
from app.modules.email_processor.storage import _optimize_image

input_path = "example/IMG_8064.png"
output_path = "reproduced_optimized.jpeg"

def test_optimization():
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    original_size = os.path.getsize(input_path)
    print(f"Original Size: {original_size / 1024 / 1024:.2f} MB")

    with open(input_path, "rb") as f:
        content = f.read()

    optimized = _optimize_image(content)
    
    with open(output_path, "wb") as f:
        f.write(optimized)
        
    optimized_size = len(optimized)
    print(f"Optimized Size: {optimized_size / 1024 / 1024:.2f} MB")
    print(f"Reduction: {(1 - optimized_size/original_size)*100:.2f}%")

if __name__ == "__main__":
    test_optimization()
