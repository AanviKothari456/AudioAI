import sounddevice as sd
import librosa
import numpy as np
import torch
import torch.nn as nn

# === Load your trained model ===

class AudioNet(nn.Module):
    def __init__(self):
        super(AudioNet, self).__init__()
        self.fc1 = nn.Linear(13, 64)
        self.fc2 = nn.Linear(64, 32)
        self.out = nn.Linear(32, 2)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.out(x)

model = AudioNet()
model.load_state_dict(torch.load("model.pth"))  # make sure you saved it after training!
model.eval()

# === Predict function ===

def predict_from_audio(audio, sr):
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1).reshape(1, -1)
    x_tensor = torch.tensor(mfcc_mean, dtype=torch.float32)
    with torch.no_grad():
        output = model(x_tensor)
        pred = torch.argmax(output, dim=1).item()
    return pred

# === Record from mic ===

def record_audio(seconds=2, sr=16000):
    print("🎙️ Speak now...")
    audio = sd.rec(int(sr * seconds), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    audio = audio.flatten()  # convert to 1D
    return audio, sr

# === Class map ===
class_map = {
    0: "hello",
    1: "cheers"
}

# === Main loop ===
if __name__ == "__main__":
    while True:
        audio, sr = record_audio()
        pred = predict_from_audio(audio, sr)
        print(f"🔊 I heard: {class_map[pred]}")
        cont = input("Do another? (y/n): ")
        if cont.lower() != "y":
            break
