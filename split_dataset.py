import os
import shutil
import random
from tqdm import tqdm

# Set seed agar acakan konsisten
random.seed(42)

# Rasio pembagian
train_ratio = 0.8
val_ratio = 0.2

# Path direktori
base_dir = os.path.dirname(os.path.abspath(__file__))
source_dir = os.path.join(base_dir, 'dataset', 'dataset_merged')
train_dir = os.path.join(base_dir, 'dataset', 'dataset_train')
val_dir = os.path.join(base_dir, 'dataset', 'dataset_val')


for dir_path in [train_dir, val_dir]:
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path)


for class_name in os.listdir(source_dir):
    class_path = os.path.join(source_dir, class_name)
    if not os.path.isdir(class_path):
        continue

    images = os.listdir(class_path)
    random.shuffle(images)

    train_count = int(len(images) * train_ratio)

    train_images = images[:train_count]
    val_images = images[train_count:]

    
    os.makedirs(os.path.join(train_dir, class_name), exist_ok=True)
    os.makedirs(os.path.join(val_dir, class_name), exist_ok=True)

    
    for img in tqdm(train_images, desc=f"[Train] {class_name}"):
        src = os.path.join(class_path, img)
        dst = os.path.join(train_dir, class_name, img)
        shutil.copyfile(src, dst)

    
    for img in tqdm(val_images, desc=f"[Val] {class_name}"):
        src = os.path.join(class_path, img)
        dst = os.path.join(val_dir, class_name, img)
        shutil.copyfile(src, dst)

print("\n✅ Dataset berhasil dibagi ke dalam folder 'dataset_train' dan 'dataset_val'.")
