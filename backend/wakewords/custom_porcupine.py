import os
import ctypes
from ctypes import *
import struct

class CustomPorcupine:
    """
    Custom Porcupine implementation that uses a dummy access key.
    This uses the C library directly with ctypes.
    """
    class PorcupineStatuses:
        SUCCESS = 0
        OUT_OF_MEMORY = 1
        IO_ERROR = 2
        INVALID_ARGUMENT = 3
        # ... other status codes as needed

    class CPorcupine(Structure):
        pass

    def __init__(self, library_path, model_path, keyword_paths, sensitivities):
        """
        Constructor using a dummy access key.
        
        Args:
            library_path: Path to Porcupine's dynamic library (.so file)
            model_path: Path to the model parameters file
            keyword_paths: List of paths to keyword model files
            sensitivities: List of sensitivity values (0-1) for each keyword
        """
        if not os.path.exists(library_path):
            raise IOError(f"Couldn't find Porcupine's dynamic library at '{library_path}'.")
        if not os.path.exists(model_path):
            raise IOError(f"Couldn't find model file at '{model_path}'.")
        
        for kw_path in keyword_paths:
            if not os.path.exists(kw_path):
                raise IOError(f"Couldn't find keyword file at '{kw_path}'.")
        
        for sens in sensitivities:
            if not (0 <= sens <= 1):
                raise ValueError("Sensitivity values must be between 0 and 1.")
                
        if len(keyword_paths) != len(sensitivities):
            raise ValueError("Number of keywords must match the number of sensitivities.")
        
        # Load the Porcupine C library
        self.library = cdll.LoadLibrary(library_path)
        
        # Define function signatures
        self.library.pv_porcupine_init.argtypes = [
            c_char_p,      # access_key
            c_char_p,      # model_path
            c_int,         # num_keywords
            POINTER(c_char_p),  # keyword_paths
            POINTER(c_float),   # sensitivities
            POINTER(POINTER(self.CPorcupine))  # object
        ]
        self.library.pv_porcupine_init.restype = c_int
        
        self.library.pv_porcupine_delete.argtypes = [POINTER(self.CPorcupine)]
        self.library.pv_porcupine_delete.restype = None
        
        self.library.pv_porcupine_process.argtypes = [
            POINTER(self.CPorcupine),
            POINTER(c_short),
            POINTER(c_int)
        ]
        self.library.pv_porcupine_process.restype = c_int
        
        self.library.pv_porcupine_frame_length.restype = c_int
        self.library.pv_sample_rate.restype = c_int
        
        # Initialize the Porcupine instance
        self._handle = POINTER(self.CPorcupine)()
        
        # Convert keyword paths to C-compatible format
        c_keyword_paths = (c_char_p * len(keyword_paths))(*[os.path.abspath(kw).encode('utf-8') for kw in keyword_paths])
        c_sensitivities = (c_float * len(sensitivities))(*sensitivities)
        
        # Use a dummy access key that matches the expected format (32-character alphanumeric string)
        # This is for local testing only and won't authenticate with Picovoice services
        dummy_key = "0123456789abcdef0123456789abcdef"
        
        status = self.library.pv_porcupine_init(
            dummy_key.encode('utf-8'),
            model_path.encode('utf-8'),
            len(keyword_paths),
            c_keyword_paths,
            c_sensitivities,
            byref(self._handle)
        )
        
        if status != self.PorcupineStatuses.SUCCESS:
            raise Exception(f"Failed to initialize Porcupine. Status code: {status}")
            
        # Get frame length and sample rate
        self._frame_length = self.library.pv_porcupine_frame_length()
        self._sample_rate = self.library.pv_sample_rate()
    
    def delete(self):
        """
        Releases resources acquired by Porcupine.
        """
        if hasattr(self, '_handle') and self._handle:
            self.library.pv_porcupine_delete(self._handle)
            self._handle = None
    
    def process(self, pcm):
        """
        Processes an audio frame and returns the detection result.
        
        Args:
            pcm: A frame of audio samples (16-bit, signed integers)
            
        Returns:
            Index of detected keyword, or -1 if no keyword was detected
        """
        if len(pcm) != self.frame_length:
            raise ValueError(f"Invalid frame length. Expected {self.frame_length}, got {len(pcm)}")
            
        result = c_int()
        status = self.library.pv_porcupine_process(
            self._handle,
            (c_short * len(pcm))(*pcm),
            byref(result)
        )
        
        if status != self.PorcupineStatuses.SUCCESS:
            raise Exception(f"Failed to process audio frame. Status code: {status}")
            
        return result.value
    
    @property
    def frame_length(self):
        """
        Number of audio samples per frame.
        """
        return self._frame_length
    
    @property
    def sample_rate(self):
        """
        Audio sample rate expected by Porcupine.
        """
        return self._sample_rate
        
def create(library_path, model_path, keyword_paths, sensitivities=None):
    """
    Factory function for creating a CustomPorcupine instance.
    
    Args:
        library_path: Path to Porcupine's dynamic library
        model_path: Path to the model parameters file
        keyword_paths: List of paths to keyword model files
        sensitivities: Optional list of sensitivity values (default: [0.5] * len(keyword_paths))
        
    Returns:
        An instance of CustomPorcupine
    """
    if sensitivities is None:
        sensitivities = [0.5] * len(keyword_paths)
        
    return CustomPorcupine(
        library_path=library_path,
        model_path=model_path,
        keyword_paths=keyword_paths,
        sensitivities=sensitivities
    )