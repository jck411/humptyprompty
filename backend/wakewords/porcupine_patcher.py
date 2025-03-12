#!/usr/bin/env python3
import os
import sys
import shutil
import tempfile
import mmap
import re
import subprocess

class PorcupinePatcher:
    """
    Attempts to patch the Porcupine shared library to bypass access key verification.
    This is an experimental approach that directly modifies the binary.
    """
    
    def __init__(self, library_path):
        """
        Initialize the patcher with the path to the Porcupine library.
        
        Args:
            library_path: Path to the Porcupine shared library (.so file)
        """
        if not os.path.exists(library_path):
            raise FileNotFoundError(f"Library not found: {library_path}")
            
        self.original_library_path = library_path
        self.temp_dir = None
        self.patched_library_path = None
        
    def create_patched_library(self):
        """
        Create a patched copy of the library with disabled access key validation.
        
        Returns:
            Path to the patched library
        """
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="porcupine_patch_")
        self.patched_library_path = os.path.join(self.temp_dir, os.path.basename(self.original_library_path))
        
        # Copy the original library to our temp directory
        shutil.copy2(self.original_library_path, self.patched_library_path)
        
        # Apply patches
        self._apply_patches()
        
        print(f"[WakeWord] Created patched library at {self.patched_library_path}")
        return self.patched_library_path
        
    def _apply_patches(self):
        """Apply multiple patch strategies to bypass key verification"""
        success = False
        
        # Get detailed information about the library init function using nm
        print("[WakeWord] Analyzing library for init function...")
        try:
            result = subprocess.run(
                ['nm', '-D', '--defined-only', self.patched_library_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                init_func_addr = None
                for line in result.stdout.splitlines():
                    if 'pv_porcupine_init' in line:
                        parts = line.split()
                        if len(parts) >= 3 and parts[1].lower() in ['t', 'w']:  # Text or weak symbol
                            init_func_addr = parts[0]
                            print(f"[WakeWord] Found pv_porcupine_init at address: {init_func_addr}")
                            break
                
                if init_func_addr:
                    # Use objdump to get more detailed info about the function
                    result = subprocess.run(
                        ['objdump', '-d', '--start-address=0x' + init_func_addr, self.patched_library_path],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        print("[WakeWord] Retrieved disassembly of init function")
                
        except Exception as e:
            print(f"[WakeWord] Error analyzing library: {e}")
        
        # Try all patching methods, from least to most aggressive
        
        # Patch method 1: Find error code returns in init function and change them to success
        if self._patch_init_error_returns():
            success = True
            print("[WakeWord] Successfully patched init error returns.")
            
        # Patch method 2: Find access key check logic in init function and bypass it
        if self._patch_access_key_validation():
            success = True
            print("[WakeWord] Successfully patched access key validation.")
            
        # Patch method 3: More aggressive pattern matching and patching
        if self._patch_known_validation_patterns():
            success = True
            print("[WakeWord] Successfully patched known validation patterns.")

        # Patch method 4: Find strings related to access keys and patch code that references them
        if self._patch_access_key_strings():
            success = True
            print("[WakeWord] Successfully patched access key string references.")
        
        # Patch method 5: Try a JMP patch at key validation points
        if self._patch_with_jump():
            success = True
            print("[WakeWord] Successfully patched with jump instructions.")
            
        if not success:
            print("[WakeWord] Warning: None of the patching methods reported success.")
            
    def _patch_init_error_returns(self):
        """
        Patch the pv_porcupine_init function to return success code even when it would fail on validation
        """
        try:
            with open(self.patched_library_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                
                # Common pattern: Compare something, then return error code 3 (INVALID_ARGUMENT)
                # We'll replace the error return with a success return
                
                # Find the init function
                init_func = mm.find(b'pv_porcupine_init')
                if init_func == -1:
                    print("[WakeWord] Couldn't find pv_porcupine_init function")
                    mm.close()
                    return False
                
                # Look around the init function for error code patterns
                search_range_start = max(0, init_func - 2000)
                search_range_end = min(mm.size(), init_func + 5000)
                
                # Common error code sequences
                error_patterns = [
                    # mov eax, 3; ret  (INVALID_ARGUMENT)
                    (b'\xb8\x03\x00\x00\x00\xc3', b'\xb8\x00\x00\x00\x00\xc3'),
                    
                    # test/cmp something, jne -> skip jne
                    (b'\x74\x02\xb8\x03', b'\x90\x90\xb8\x00'),  # je X; mov eax, 3 -> nop nop; mov eax, 0
                    
                    # test/cmp something, je -> always jump
                    (b'\x85\xc0\x75', b'\x85\xc0\xeb'),  # test eax, eax; jne -> test eax, eax; jmp
                    
                    # Some compare followed by conditional jump + error return
                    (b'\x75.\xb8\x03\x00\x00\x00', b'\xeb.\xb8\x00\x00\x00\x00'),  # jne X; mov eax, 3 -> jmp X; mov eax, 0
                    
                    # Compare zero, jump if not equal, then error
                    (b'\x48\x83\xf8\x00\x75.\xb8\x03', b'\x48\x83\xf8\x00\xeb.\xb8\x00'),
                ]
                
                modified = False
                for pattern, replacement in error_patterns:
                    # Look for the pattern in the range around the init function
                    pos = search_range_start
                    while pos < search_range_end:
                        pos = mm.find(pattern, pos, search_range_end)
                        if pos == -1:
                            break
                        
                        # Check if this pattern allows wildcards (indicated by . in the pattern)
                        if b'.' in pattern:
                            # We need to preserve the jump offset
                            p_list = list(pattern)
                            r_list = list(replacement)
                            for i, b in enumerate(p_list):
                                if b == ord('.'):
                                    r_list[i] = mm[pos + i]
                            
                            mm[pos:pos+len(pattern)] = bytes(r_list)
                        else:
                            # Simple replacement
                            mm[pos:pos+len(pattern)] = replacement
                            
                        pos += len(replacement)
                        modified = True
                        print(f"[WakeWord] Patched init error return at offset {pos - len(replacement)}")
                
                mm.close()
                return modified
                
        except Exception as e:
            print(f"[WakeWord] Error patching init error returns: {e}")
            return False
            
    def _patch_access_key_validation(self):
        """
        Patch the code that validates the access key to always pass
        """
        try:
            # Look for functions that might validate the access key
            result = subprocess.run(
                ['strings', '-a', '-t', 'x', self.patched_library_path], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0:
                print(f"[WakeWord] strings command failed: {result.stderr}")
                return False
            
            # Look for strings related to access key validation
            key_related_strings = []
            for line in result.stdout.splitlines():
                parts = line.strip().split(' ', 1)
                if len(parts) == 2:
                    offset_hex, string = parts
                    try:
                        offset = int(offset_hex, 16)
                        # Look for strings related to key validation
                        if any(term in string.lower() for term in ['access', 'key', 'license', 'valid']):
                            key_related_strings.append((offset, string))
                    except ValueError:
                        continue
            
            if not key_related_strings:
                print("[WakeWord] No key-related strings found")
                return False
            
            with open(self.patched_library_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                
                modified = False
                # For each key-related string
                for offset, string in key_related_strings:
                    print(f"[WakeWord] Found key-related string at {offset}: {string}")
                    
                    # Look for code references to these strings
                    # This is a simplistic approach - look for load address patterns
                    # that might be referencing this string
                    for i in range(offset - 5000, offset + 5000):
                        if i >= 0 and i + 4 < mm.size():
                            # Check if there's a potential reference to the string offset
                            # (simplistic - just look for the offset as a 4-byte value)
                            if int.from_bytes(mm[i:i+4], byteorder='little') == offset:
                                # This might be a reference to the string - patch code after it
                                patch_pos = i + 4
                                if patch_pos + 10 < mm.size():
                                    # Look for a conditional jump within the next few bytes
                                    for j in range(patch_pos, patch_pos + 20):
                                        # Check for common conditional jump opcodes
                                        if mm[j] in [0x74, 0x75, 0x84, 0x85]:  # je, jne, test, etc.
                                            # Replace with nop or unconditional jump
                                            if mm[j] in [0x74, 0x75]:  # je, jne
                                                mm[j] = 0xeb  # jmp
                                                modified = True
                                                print(f"[WakeWord] Patched conditional jump at {j}")
                                            elif mm[j] in [0x84, 0x85]:  # test
                                                mm[j:j+2] = b'\x90\x90'  # nop nop
                                                modified = True
                                                print(f"[WakeWord] Patched test at {j}")
                
                mm.close()
                return modified
                
        except Exception as e:
            print(f"[WakeWord] Error patching access key validation: {e}")
            return False
            
    def _patch_known_validation_patterns(self):
        """
        Patch known binary patterns that might be related to validation
        """
        try:
            with open(self.patched_library_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                
                # More specific patterns that might be access key validation
                validation_patterns = [
                    # test rax, rax; je X -> always jump
                    (b'\x48\x85\xc0\x74', b'\x48\x85\xc0\xeb'),
                    
                    # test rax, rax; jne X -> never jump
                    (b'\x48\x85\xc0\x75', b'\x48\x85\xc0\x90\x90'),
                    
                    # cmp byte ptr [rax], 0; jne X -> never jump
                    (b'\x80\x38\x00\x75', b'\x80\x38\x00\x90\x90'),
                    
                    # access key length check - 32 chars
                    (b'\x48\x83\xf8\x20\x75', b'\x48\x83\xf8\x20\xeb'),  # cmp rax, 0x20; jne X -> jmp X
                    
                    # call to validation function + test result
                    (b'\xe8....\x85\xc0\x75', b'\x90\x90\x90\x90\x90\x85\xc0\xeb'),
                    
                    # mov eax, 3; leave; ret  (common error return sequence)
                    (b'\xb8\x03\x00\x00\x00\xc9\xc3', b'\xb8\x00\x00\x00\x00\xc9\xc3'),
                ]
                
                modified = False
                for pattern, replacement in validation_patterns:
                    # If pattern contains wildcards (...)
                    if b'.' in pattern:
                        # Find using regex
                        pattern_regex = pattern.replace(b'.', b'.')
                        pattern_regex = re.compile(pattern_regex)
                        
                        # Search for the pattern
                        pos = 0
                        while pos < mm.size() - len(pattern):
                            search_region = mm[pos:pos + 2000]  # Search in chunks
                            match = pattern_regex.search(search_region)
                            if not match:
                                pos += 2000 - len(pattern)  # Move search window
                                continue
                                
                            match_pos = pos + match.start()
                            
                            # Build replacement preserving wildcards
                            actual_replacement = bytearray(replacement)
                            j = 0
                            for i, b in enumerate(pattern):
                                if b == ord('.'):
                                    if j < len(replacement) and replacement[j] == ord('.'):
                                        actual_replacement[j] = mm[match_pos + i]
                                    j += 1
                            
                            # Apply patch
                            mm[match_pos:match_pos+len(pattern)] = bytes(actual_replacement)
                            pos = match_pos + len(replacement)
                            modified = True
                            print(f"[WakeWord] Patched pattern at offset {match_pos}")
                    else:
                        # Simple pattern search
                        pos = 0
                        while True:
                            pos = mm.find(pattern, pos)
                            if pos == -1:
                                break
                                
                            # Replace pattern
                            mm[pos:pos+len(pattern)] = replacement
                            pos += len(replacement)
                            modified = True
                            print(f"[WakeWord] Patched pattern at offset {pos - len(replacement)}")
                
                mm.close()
                return modified
                
        except Exception as e:
            print(f"[WakeWord] Error patching known validation patterns: {e}")
            return False
            
    def _patch_access_key_strings(self):
        """
        Find and modify strings related to access keys
        """
        try:
            with open(self.patched_library_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                
                # Look for specific strings related to access keys
                strings_to_patch = [
                    b'access_key',
                    b'AccessKey',
                    b'access key',
                    b'invalid access key',
                    b'activation error',
                ]
                
                modified = False
                for string in strings_to_patch:
                    pos = 0
                    while True:
                        pos = mm.find(string, pos)
                        if pos == -1:
                            break
                        
                        # Replace with innocuous string of same length (to maintain string table)
                        replaced = b'_' * len(string)
                        mm[pos:pos+len(string)] = replaced
                        pos += len(string)
                        modified = True
                        print(f"[WakeWord] Patched string '{string.decode('utf-8', errors='ignore')}' at offset {pos - len(string)}")
                
                mm.close()
                return modified
                
        except Exception as e:
            print(f"[WakeWord] Error patching access key strings: {e}")
            return False
            
    def _patch_with_jump(self):
        """
        Try to identify the entry of the access key validation routine and bypass it
        """
        try:
            # Find the init function start and end addresses
            result = subprocess.run(
                ['objdump', '-d', self.patched_library_path], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0:
                print(f"[WakeWord] objdump failed: {result.stderr}")
                return False
            
            # Extract the pv_porcupine_init function
            init_func_start = None
            init_func_end = None
            init_func_lines = []
            
            in_init_func = False
            for line in result.stdout.splitlines():
                if not in_init_func:
                    if 'pv_porcupine_init>' in line:
                        in_init_func = True
                        # Extract the starting address
                        try:
                            init_func_start = int(line.split(':')[0].strip(), 16)
                        except (ValueError, IndexError):
                            pass
                        init_func_lines.append(line)
                else:
                    if '>:' in line and 'pv_porcupine_init>' not in line:
                        # We've reached the next function
                        in_init_func = False
                        try:
                            # The end is just before the next function
                            init_func_end = int(line.split(':')[0].strip(), 16)
                        except (ValueError, IndexError):
                            pass
                    else:
                        init_func_lines.append(line)
            
            if init_func_start is None:
                print("[WakeWord] Couldn't find pv_porcupine_init function boundaries")
                return False
            
            # Look for patterns of access key validation and related jumps
            key_validation_offset = None
            success_return_offset = None
            
            # Analyze function lines for validation patterns
            for line in init_func_lines:
                # Look for branching after access key check
                if 'test' in line and 'rax' in line and '%rax' in line:
                    # This might be testing a value returned from key validation
                    next_line_idx = init_func_lines.index(line) + 1
                    if next_line_idx < len(init_func_lines):
                        next_line = init_func_lines[next_line_idx]
                        if any(jmp in next_line for jmp in ['je', 'jne', 'jz']):
                            try:
                                # Extract the address from the current line
                                addr = int(line.split(':')[0].strip(), 16)
                                key_validation_offset = addr
                                print(f"[WakeWord] Potential key validation at 0x{key_validation_offset:x}")
                            except (ValueError, IndexError):
                                pass
                
                # Look for successful return label
                if 'xor' in line and '%eax' in line and '%eax' in line:
                    # This might be setting return value to 0 (success)
                    try:
                        addr = int(line.split(':')[0].strip(), 16)
                        success_return_offset = addr
                        print(f"[WakeWord] Potential success return at 0x{success_return_offset:x}")
                    except (ValueError, IndexError):
                        pass
            
            # If we found both validation and success return, try to patch
            if key_validation_offset and success_return_offset:
                with open(self.patched_library_path, 'r+b') as f:
                    mm = mmap.mmap(f.fileno(), 0)
                    
                    # Calculate the file offsets from virtual addresses
                    # This is a simplification - in a real executable, we'd need to consider the section offset
                    validation_file_offset = key_validation_offset
                    success_file_offset = success_return_offset
                    
                    # Insert an unconditional jump from validation to success
                    # Jump opcode: 0xe9 + 4-byte offset
                    jump_distance = success_file_offset - (validation_file_offset + 5)
                    jump_bytes = bytes([0xe9]) + jump_distance.to_bytes(4, byteorder='little', signed=True)
                    
                    # Write the jump instruction
                    mm[validation_file_offset:validation_file_offset + 5] = jump_bytes
                    
                    mm.close()
                    print(f"[WakeWord] Inserted jump from 0x{validation_file_offset:x} to 0x{success_file_offset:x}")
                    return True
            
            return False
                
        except Exception as e:
            print(f"[WakeWord] Error patching with jump: {e}")
            return False
    
    def cleanup(self):
        """
        Clean up temporary directories and files
        """
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self.patched_library_path = None
        except Exception as e:
            print(f"[WakeWord] Error during cleanup: {e}")

def create_patched_library(library_path):
    """
    Create a patched version of the Porcupine library with access key verification removed
    
    Args:
        library_path: Path to the original Porcupine library
        
    Returns:
        Path to the patched library
    """
    patcher = PorcupinePatcher(library_path)
    return patcher.create_patched_library()