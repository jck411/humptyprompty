import torch
import torch.onnx

def convert_model(model_path):
    # Load the PyTorch model
    model = torch.load(model_path, map_location=torch.device('cpu'))
    model.eval()
    
    # Create dummy input tensor (adjust shape based on your model's input requirements)
    # Typical wake word models expect audio features as input
    dummy_input = torch.randn(1, 1, 16000)  # Batch size 1, 1 channel, 16000 samples
    
    # Convert to ONNX
    output_path = model_path.replace('.pth', '.onnx')
    torch.onnx.export(
        model,               # PyTorch model
        dummy_input,         # Dummy input
        output_path,         # Output file path
        export_params=True,  # Store the trained parameter weights inside the model file
        opset_version=11,   # ONNX version to export the model to
        do_constant_folding=True,  # Whether to execute constant folding
        input_names=['input'],   # Model's input names
        output_names=['output'], # Model's output names
        dynamic_axes={
            'input': {0: 'batch_size'},  # Variable length axes
            'output': {0: 'batch_size'}
        }
    )
    print(f"Model converted and saved to {output_path}")

if __name__ == "__main__":
    model_path = "wake_word_model_best.pth"
    convert_model(model_path)