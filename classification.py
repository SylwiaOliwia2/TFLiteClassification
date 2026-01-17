import numpy as np
from PIL import Image
import tensorflow as tf


# Load the TFLite model and allocate tensors.
interpreter = tf.lite.Interpreter(model_path="mobilenet_v1_1.0_224_quant.tflite")
interpreter.allocate_tensors()

# Get input and output tensors.
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

im = Image.open("animal.jpg")
res_im = im.resize((224, 224))
np_res_im = np.array(res_im)
np_res_im = (np_res_im).astype('uint8')

if len(np_res_im.shape) == 3:
    np_res_im = np.expand_dims(np_res_im, 0)
# Test the model on random input data.
input_shape = input_details[0]['shape']
input_data = np_res_im
interpreter.set_tensor(input_details[0]['index'], input_data)

interpreter.invoke()

# The function `get_tensor()` returns a copy of the tensor data.
# Use `tensor()` in order to get a pointer to the tensor.
output_data = interpreter.get_tensor(output_details[0]['index'])

classification_prob = []
classification_label = []
total = 0
for index,prob in enumerate(output_data[0]):
    if prob != 0:
        classification_prob.append(prob)
        total += prob
        classification_label.append(index)

label_names = [line.rstrip('\n') for line in open("labels_mobilenet_quant_v1_224.txt")]
found_labels = np.array(label_names)[classification_label]

# Calculate probabilities and pair with labels
probabilities = classification_prob / total
label_prob_pairs = list(zip(found_labels, probabilities))
# Sort by probability in descending order
sorted_pairs = sorted(label_prob_pairs, key=lambda x: x[1], reverse=True)

# WTemporary solution - save as a text file
with open("results.txt", "w") as f:
    for label, prob in sorted_pairs:
        f.write(f"{label}\t{prob}\n")
