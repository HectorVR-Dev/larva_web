import torch
        
def verificar_gpu():

    if torch.cuda.is_available():
        print(f"✅ GPU disponible: {torch.cuda.get_device_name()}")
        print(f"💾 Memoria GPU total: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        print(f"💾 Memoria GPU ocupada: {torch.cuda.memory_reserved(0) / 1e9:.1f} GB")
        return 
    else:
        print("❌ GPU no disponible")
        return
