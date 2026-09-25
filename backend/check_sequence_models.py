from tensorflow.keras.models import load_model


lstm_model = load_model("models/lstm.keras")
gru_model = load_model("models/gru.keras")


print("=" * 50)
print("LSTM MODEL")
print("=" * 50)

print("Input shape:", lstm_model.input_shape)
print("Output shape:", lstm_model.output_shape)
print("Number of layers:", len(lstm_model.layers))


print("\n" + "=" * 50)
print("GRU MODEL")
print("=" * 50)

print("Input shape:", gru_model.input_shape)
print("Output shape:", gru_model.output_shape)
print("Number of layers:", len(gru_model.layers))