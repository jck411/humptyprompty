# Speech-to-Text (STT) System Overview

This project implements a Speech-to-Text (STT) system with a modular design that supports multiple providers (e.g., Azure). The architecture ensures that all STT functionality respects a global configuration flag (`STT_ENABLED`), allowing dynamic control of the system at runtime.

## Architecture Overview

The system is divided into two primary modules:

1. **Base STT Provider (`backend/stt/base.py`)**  
   This abstract class (`BaseSTTProvider`) defines the common interface and shared logic for all STT providers. It is responsible for:
   - Managing the overall state of the STT service (READY, IDLE, LISTENING, PAUSED, ERROR).
   - Holding a unified configuration (passed as a configuration object) that contains the `enabled` flag along with other provider-specific settings.
   - Implementing high-level methods (`start_listening`, `stop_listening`, and `pause_listening`) that check the global enabled state before performing any actions.

2. **Azure STT Provider (`backend/stt/azure_stt.py`)**  
   This concrete implementation extends `BaseSTTProvider` and implements the provider-specific logic required to integrate with the Azure Speech SDK:
   - **Setup:** Initializes the recognizer with the proper Azure credentials and configuration.
   - **Event Callbacks:** Processes recognized speech (both interim and final results) by checking the configuration in real-time to prevent processing if STT has been disabled.
   - **Provider Methods:** Implements the low-level methods (`_start_listening_impl`, `_stop_listening_impl`, `_pause_listening_impl`) required by the base class.

## Configuration and Global Control

The configuration is centralized and includes a `GENERAL_AUDIO` section with a global flag (`STT_ENABLED`). This flag is passed to the STT provider configuration, ensuring that:

- **At Startup:** The provider checks whether STT is enabled and either sets up the recognizer or remains in a paused state.
- **During Runtime:** Both the base class methods and the provider’s event callbacks check the configuration. This dual-layer check ensures that any change to the global enabled state is applied immediately. For example:
  - **Base Class:** Prevents starting the listening process if STT is disabled.
  - **Event Callbacks:** Stop processing any incoming speech if the configuration is updated to disable STT while already running.

## How the Files Work Together

1. **Base Provider (`backend/stt/base.py`):**
   - **Configuration Handling:** Stores the full configuration (including `enabled` flag) as the single source of truth.
   - **Control Methods:** Implements `start_listening`, `stop_listening`, and `pause_listening`, all of which check `self.config.enabled` before proceeding.
   - **Abstract Methods:** Defines abstract methods that each provider must implement to handle provider-specific tasks.

2. **Azure Provider (`backend/stt/azure_stt.py`):**
   - **Initialization:** In the constructor, the Azure provider passes its configuration to the base class and sets up the recognizer if STT is enabled.
   - **Setup:** Implements `setup_recognizer` to create a speech configuration using Azure credentials and attach event listeners.
   - **Event Callbacks:** Both `handle_final_result` and `handle_interim_result` check the configuration (`self.config.enabled`) to ensure that if STT is toggled off during operation, no speech data is queued for processing.
   - **Provider-Specific Methods:** Implements the low-level start, stop, and pause methods required by the base class.

3. **Global Configuration:**
   - The global configuration is defined externally (typically in a configuration file or environment variables) and is used to initialize the provider.
   - This design makes it possible to switch providers easily as long as the new provider adheres to the interface defined by `BaseSTTProvider`.

## Benefits of This Approach

- **Consistency:**  
  All STT providers follow the same interface and honor the same global configuration. This minimizes the risk of inconsistencies when switching providers or making runtime changes.

- **Dynamic Control:**  
  By having configuration checks both in the base class and within the provider’s event callbacks, any change to the global enabled state is immediately effective. This prevents the system from processing speech data when STT is turned off, even if the recognizer is already active.

- **Modularity and Extensibility:**  
  The separation between the base class and the provider implementations allows for easier maintenance and the addition of new providers without impacting the rest of the system.

## How to Use

1. **Configure the System:**  
   Ensure your configuration file includes the `GENERAL_AUDIO` section with the `STT_ENABLED` flag set appropriately. Also, provide Azure credentials if using the Azure provider.

2. **Start the Service:**  
   On startup, the Azure provider checks the configuration. If enabled, it sets up the recognizer and transitions to the READY state.

3. **Runtime Changes:**  
   When you toggle the `STT_ENABLED` flag (via a REST endpoint or other configuration mechanism), both the base class and the provider’s callbacks will immediately enforce the new state.

---

This README should help you and other developers understand how the STT system is designed, how the files interact, and the benefits of centralizing configuration checks across the application.
