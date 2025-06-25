import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import json
import os

# Load model
model = load_model('model/model_mobilenetv2_final_80.h5')


label_map = {
    0: 'akiec',
    1: 'bcc',
    2: 'bkl',
    3: 'df',
    4: 'mel',
    5: 'nv',
    6: 'vasc'
}

def predict_image(img_path):
    img = image.load_img(img_path, target_size=(224, 224))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    prediction = model.predict(img_array)[0]
    predicted_index = np.argmax(prediction)
    confidence = round(float(np.max(prediction)) * 100, 2)

    predicted_label = label_map[predicted_index]
    return predicted_label, confidence
