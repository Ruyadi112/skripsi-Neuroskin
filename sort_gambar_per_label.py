import pandas as pd
import shutil
import os

# Path ke file CSV dan gambar
metadata_path = 'HAM10000_metadata.csv'
source_folder = 'dataset/dataset_merged'

# Baca CSV
df = pd.read_csv(metadata_path)


for label in df['dx'].unique():
    os.makedirs(os.path.join(source_folder, label), exist_ok=True)

# Pindahkan gambar ke folder label-nya
for _, row in df.iterrows():
    img_name = row['image_id'] + '.jpg'
    label = row['dx']
    src = os.path.join(source_folder, img_name)
    dst = os.path.join(source_folder, label, img_name)
    if os.path.exists(src):
        shutil.move(src, dst)

print("✅ Gambar berhasil dipindahkan ke folder kelas.")
