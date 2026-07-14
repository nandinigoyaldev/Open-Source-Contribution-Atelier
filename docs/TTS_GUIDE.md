# Text-to-Speech (TTS) Engine Architecture

This document outlines the architecture, workflow, and best practices for the Text-to-Speech (TTS) feature implemented in the Parampara platform.

## Architecture

The TTS engine is built using the native browser `window.speechSynthesis` API (Web Speech API). It is encapsulated primarily within the `useTextToSpeech` custom React hook, which manages state and provides a unified interface for the rest of the application.

### Key Components
1. **`useTextToSpeech` Hook (`frontend/src/hooks/useTextToSpeech.ts`)**:
   - Manages the core synthesis logic.
   - Handles asynchronous voice loading (`onvoiceschanged`).
   - Maintains state for playing/paused status and user settings (voice URI, rate, pitch, volume).
   - Provides methods: `play`, `pause`, `stop`, `restart`, `playPreview`, and `setSettings`.

2. **`TextToSpeechControls` Component (`frontend/src/components/ui/TextToSpeechControls.tsx`)**:
   - Renders the UI for playback control (Play, Pause, Stop).
   - Includes an expandable settings popover for real-time voice customization.

## Speech Customization Workflow

1. **User Interaction**: The user opens the TTS settings from the `TextToSpeechControls` UI.
2. **Settings Modification**: Changes to Voice, Speed, Pitch, or Volume immediately update the `settings` state via `setSettings`.
3. **Persistence**: `setSettings` saves the updated configuration to `localStorage` under the key `tts_settings`.
4. **Real-time Application**: If audio is currently playing, the hook automatically detects the change and triggers a `restart()` to apply the new settings seamlessly without requiring page reload.

## Preference Persistence Strategy

User preferences are persisted locally on the client using `localStorage` to ensure privacy and cross-session continuity.

- **Key**: `tts_settings`
- **Format**: JSON representation of `TTSSettings` (`{ voiceURI, rate, pitch, volume }`).
- **Loading**: Settings are loaded synchronously when `useTextToSpeech` mounts. If a saved voice is no longer available (e.g., accessed from a different device), the system gracefully falls back to a default voice.

## Browser Compatibility Considerations

- **Asynchronous Voice Loading**: Some browsers (like Chrome) load voices asynchronously. The hook listens to `window.speechSynthesis.onvoiceschanged` to populate the voice list dynamically.
- **Unsupported Environments**: If `window.speechSynthesis` is missing, the hook gracefully sets `isSupported = false`, and the UI simply hides the TTS controls to avoid errors.
- **Volume**: Some browsers ignore the volume property on `SpeechSynthesisUtterance`. The UI exposes it, but it may not take effect universally.

## Fallback Behavior

1. **Voice Selection**: If the user's preferred voice (from `localStorage`) is missing, the engine tries to find a premium English voice (like Siri, Alex, or Google).
2. **Next Fallback**: If no premium voice is found, it falls back to the first available English voice.
3. **Final Fallback**: It falls back to the system default voice.

## Accessibility Guidelines

- Ensure that TTS controls are clearly visible but not intrusive.
- Use high contrast for the play/pause/settings buttons.
- Maintain keyboard navigation support for all sliders and dropdowns.
- Provide aria-labels for all interactive elements in `TextToSpeechControls`.

## Best Practices for Extending the Speech Engine

1. **New Audio Providers**: If we decide to use a cloud provider (e.g., AWS Polly, Google Cloud TTS, or ElevenLabs) in the future, the `useTextToSpeech` hook should act as an abstraction layer. The hook's return interface (`play`, `pause`, `stop`) should remain identical to prevent breaking the UI components.
2. **Language Support**: The current fallback focuses on English (`en`). If multi-language support is added, the `getBestVoice` function must be updated to respect the currently active locale or document language.
3. **Pronunciation Improvements**: To improve pronunciation of domain-specific terms (e.g., cultural/historical terms), a dictionary replacement function could be added inside the `stripMarkdown` utility or as a separate preprocessing step before passing text to `SpeechSynthesisUtterance`.
