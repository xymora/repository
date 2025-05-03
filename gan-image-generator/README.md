# 🧠 GAN Image Generator for Synthetic Image Creation

This project implements a Generative Adversarial Network (GAN) in Python using PyTorch to generate synthetic images based on the Fashion-MNIST dataset. The system trains a Generator and a Discriminator in tandem, saves model checkpoints, visualizes outputs, and evaluates the image quality using Fréchet Inception Distance (FID).

## 🎯 Objective

To generate realistic synthetic images from the Fashion-MNIST dataset using deep learning adversarial networks and evaluate them with a recognized quality metric (FID).

## 🧠 Techniques Used

- Deep Convolutional GAN (DCGAN) Architecture  
- Adversarial training with Generator and Discriminator  
- Visualization of training progress using generated image grids  
- Checkpoint saving and loading for reproducible results  
- Quality assessment with FID Score  

## 🛠️ Technologies

- Python 3.x  
- PyTorch  
- torchvision  
- matplotlib  
- numpy  
- scipy  
- Pillow  
- torch-fidelity (for FID calculation)

## 📁 Project Structure

gan-image-generator/  
├── gan_image_generator.py           # Main training loop with generator and discriminator  
├── generated_images/                # Output directory for saved image grids  
├── checkpoints/                     # Saved models for reproducibility  
├── fid_score.py                     # FID score calculation using torch-fidelity  
├── fashion_mnist_samples.png        # Grid visualization of generated images  
├── fid_result.txt                   # FID score of the generated samples  
└── README.md                        # Full project documentation

## 🚀 Pipeline

1. Load Fashion-MNIST dataset from torchvision  
2. Train GAN model for 50 epochs (configurable)  
3. Save generated images every 5 epochs  
4. Store model checkpoints (Generator and Discriminator)  
5. Evaluate image quality using FID Score  
6. Visualize results in grid format  

## 📊 Outputs

- `fashion_mnist_samples.png`: grid of 64 generated images  
- `checkpoints/`: saved generator/discriminator states  
- `fid_result.txt`: computed FID score for generated samples  

## 📌 Future Enhancements

- Extend model to support CIFAR-10 and custom datasets  
- Add conditional GAN for labeled data generation  
- Integrate TensorBoard for better training diagnostics  
- Provide API endpoint for real-time image generation
