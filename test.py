import ctranslate2
print("CTRANSLATE2 CUDA:", getattr(ctranslate2, "cuda", None) is not None)
